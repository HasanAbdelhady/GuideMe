# chat/services/ai_completion.py
import logging
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from groq import Groq
from langchain.prompts import PromptTemplate
from langchain.prompts.example_selector import LengthBasedExampleSelector

from ..config import get_default_model
from ..rag import RAG_pipeline
from .interfaces import AICompletionServiceInterface, RAGServiceInterface


class AICompletionService(AICompletionServiceInterface):
    """Service for handling AI completion operations"""

    def __init__(self, rag_service: RAGServiceInterface):
        self.logger = logging.getLogger(__name__)
        self.rag_service = rag_service

    def enforce_token_limit(
        self, messages: List[Dict], max_tokens: int = 6000
    ) -> List[Dict]:
        """Enforce token limits on message history"""
        if not messages:
            return messages

        HARD_MAX_TOKENS_API = 5800  # Slightly less than the observed 6000 limit
        SAFETY_BUFFER = 250  # Additional buffer for safety

        system_msg_list = [msg for msg in messages if msg["role"] == "system"]
        user_msg_list = [msg for msg in messages if msg["role"] == "user"]

        # Examples are historical messages (assistant, and user messages except the last one)
        examples = [
            msg
            for msg in messages
            if msg["role"] not in ("system", "user")
            or (user_msg_list and msg != user_msg_list[-1])
        ]

        if not system_msg_list or not user_msg_list:
            self.logger.warning(
                "[enforce_token_limit] Missing system or current user message. Returning messages as is, but this might lead to errors."
            )
            return messages

        system_msg = system_msg_list[0]
        current_user_msg = user_msg_list[-1].copy()

        example_prompt = PromptTemplate(
            input_variables=["role", "content"],
            template="{role}: {content}",
        )

        # Calculate tokens for system and current user message
        system_tokens = self._count_tokens([system_msg], example_prompt)
        current_user_tokens_original = self._count_tokens(
            [current_user_msg], example_prompt
        )

        self.logger.info(
            f"[enforce_token_limit] Initial token counts: System={system_tokens}, CurrentUser(Original)={current_user_tokens_original}"
        )

        # Check if current_user_msg content needs truncation
        available_for_current_user = HARD_MAX_TOKENS_API - system_tokens - SAFETY_BUFFER
        if current_user_tokens_original > available_for_current_user:
            self.logger.warning(
                f"[enforce_token_limit] Current user message content is too large "
                f"({current_user_tokens_original} tokens) for available space ({available_for_current_user} tokens). "
                f"It will be truncated."
            )
            if current_user_tokens_original > 0:  # Avoid division by zero
                proportion_to_keep = (
                    available_for_current_user / current_user_tokens_original
                )
                new_char_length = int(
                    len(current_user_msg["content"]) * proportion_to_keep * 0.9
                )
                current_user_msg["content"] = current_user_msg["content"][
                    :new_char_length
                ]
                current_user_tokens = self._count_tokens(
                    [current_user_msg], example_prompt
                )
                self.logger.info(
                    f"[enforce_token_limit] CurrentUser(Truncated) to {current_user_tokens} tokens, new char length {new_char_length}."
                )
            else:
                current_user_tokens = 0
        else:
            current_user_tokens = current_user_tokens_original

        fixed_messages_tokens = system_tokens + current_user_tokens
        max_len_for_examples = (
            HARD_MAX_TOKENS_API - fixed_messages_tokens - SAFETY_BUFFER
        )

        if max_len_for_examples < 0:
            max_len_for_examples = 0
            self.logger.warning(
                f"[enforce_token_limit] No space available for historical examples after accounting for "
                f"system ({system_tokens}), current user ({current_user_tokens}), and safety buffer ({SAFETY_BUFFER}). "
                f"Total allocated: {fixed_messages_tokens + SAFETY_BUFFER}."
            )

        selector = LengthBasedExampleSelector(
            examples=examples,
            example_prompt=example_prompt,
            max_length=max_len_for_examples,
        )

        selected_examples = selector.select_examples({})
        trimmed_messages = [system_msg] + selected_examples + [current_user_msg]

        final_estimated_tokens = self._count_tokens(trimmed_messages, example_prompt)
        self.logger.info(
            f"[enforce_token_limit] Total messages sent to LLM: {len(trimmed_messages)}, Final estimated tokens: {final_estimated_tokens} (Targeting < {HARD_MAX_TOKENS_API})"
        )

        if final_estimated_tokens >= HARD_MAX_TOKENS_API:
            self.logger.error(
                f"[enforce_token_limit] CRITICAL: Final estimated tokens ({final_estimated_tokens}) "
                f"still exceed or meet the hard API limit ({HARD_MAX_TOKENS_API}) despite truncation efforts. "
                f"This indicates a flaw in token estimation or buffer settings."
            )

        return trimmed_messages

    def _count_tokens(
        self, messages: List[Dict], prompt_template: PromptTemplate
    ) -> int:
        """Count tokens in messages using word-based estimation"""
        total = 0
        TOKEN_ESTIMATION_MULTIPLIER = 1.4
        for msg in messages:
            try:
                formatted_msg_content = prompt_template.format(**msg)
                word_count = len(formatted_msg_content.split())
                estimated_tokens = int(word_count * TOKEN_ESTIMATION_MULTIPLIER)
                total += estimated_tokens
            except KeyError:
                self.logger.warning(
                    f"Message missing role/content for token counting: {msg}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error counting tokens for message {msg}: {e}", exc_info=True
                )
        return total

    async def get_completion(
        self,
        messages: List[Dict],
        query: Optional[str] = None,
        max_tokens: int = 6500,
        chat_id: Optional[str] = None,
        is_new_chat: bool = False,
        attached_file_name: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Get AI completion from Groq"""
        groq_client_local = Groq()

        if is_new_chat:
            llm_messages = [
                {"role": msg["role"], "content": msg["content"]} for msg in messages
            ]
            completion = groq_client_local.chat.completions.create(
                model=get_default_model(),
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
            return completion.choices[0].message.content

        current_messages_copy = [msg.copy() for msg in messages]

        context_str = ""
        rag_output = ""
        if await self.rag_service.get_files_rag(chat_id) and query:
            retrieved_context_val = await sync_to_async(RAG_pipeline().retrieve_docs)(
                query, chat_id=chat_id
            )
            rag_output = retrieved_context_val
            self.logger.info(f"RAG output HERE!!!!!!!!!!! {str(rag_output)[:500]}...")
            if retrieved_context_val:
                context_str += str(retrieved_context_val)

        if context_str.strip():
            rag_info_source = (
                f" from {attached_file_name}"
                if attached_file_name
                else " from uploaded RAG documents"
            )
            if current_messages_copy and current_messages_copy[-1]["role"] == "user":
                original_user_content = current_messages_copy[-1]["content"]
                context_preamble = f'Relevant context from your uploaded documents ({rag_info_source}):\n"""{context_str}"""\n---\nOriginal query follows:\n'
                current_messages_copy[-1]["content"] = (
                    context_preamble + original_user_content
                )
            else:
                self.logger.warning(
                    "Could not find user message to prepend RAG context to."
                )

        trimmed_messages = self.enforce_token_limit(
            current_messages_copy, max_tokens=max_tokens
        )

        completion = await sync_to_async(groq_client_local.chat.completions.create)(
            model=get_default_model(),
            messages=trimmed_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        if rag_output:
            self.logger.info(f"In rag_output - returning RAG output directly.")
            return rag_output
        else:
            self.logger.info(f"No RAG output, returning LLM completion.")
            return completion.choices[0].message.content

    async def stream_completion(
        self,
        messages: List[Dict],
        query: Optional[str] = None,
        max_tokens: int = 6000,
        chat_id: Optional[str] = None,
        is_new_chat: bool = False,
        attached_file_name: Optional[str] = None,
    ):
        """Stream AI completion from Groq"""
        groq_client_local = Groq()

        if is_new_chat:
            llm_messages = [
                {"role": msg["role"], "content": msg["content"]} for msg in messages
            ]
            return groq_client_local.chat.completions.create(
                model=get_default_model(),
                messages=llm_messages,
                temperature=0.7,
                max_tokens=max_tokens,
                stream=True,
            )

        current_messages_copy = [msg.copy() for msg in messages]

        if await self.rag_service.get_files_rag(chat_id) and query:
            # Create a history string for better retrieval context
            history_str = "\n".join(
                [f"{m['role']}: {m['content']}" for m in current_messages_copy[:-1]]
            )
            # Combine history with the current query for a more informed search
            full_query_for_retrieval = (
                f"Conversation_history: {history_str}\n\nQuestion: {query}"
            )

            rag_files_debug = await self.rag_service.get_files_rag(chat_id)
            print(
                f"Files RAG From inside the services: {len(rag_files_debug)} files found"
            )

            # Pass chat_id to retrieve_docs
            try:
                retrieved_docs = await sync_to_async(RAG_pipeline().retrieve_docs)(
                    full_query_for_retrieval, chat_id=chat_id
                )
                self.logger.info(f"RAG retrieved {len(retrieved_docs)} documents")

                if retrieved_docs:
                    # Log first document preview for debugging
                    first_doc_preview = (
                        retrieved_docs[0].page_content[:200]
                        if retrieved_docs
                        else "No content"
                    )
                    self.logger.info(f"First document preview: {first_doc_preview}...")

                    # Augment the prompt
                    context_str = "\n\n".join(
                        [doc.page_content for doc in retrieved_docs]
                    )
                    rag_info_source = (
                        f" from {attached_file_name}"
                        if attached_file_name
                        else " from uploaded RAG documents"
                    )

                    if (
                        current_messages_copy
                        and current_messages_copy[-1]["role"] == "user"
                    ):
                        original_user_content = current_messages_copy[-1]["content"]
                        # Create the augmented prompt
                        context_preamble = (
                            f"Use the following context from your uploaded documents ({rag_info_source}) to answer the question.\n\n"
                            f"--- CONTEXT ---\n{context_str}\n--- END CONTEXT ---\n\n"
                            f"Based on the context, answer this question: {original_user_content}"
                        )
                        current_messages_copy[-1]["content"] = context_preamble
                        self.logger.info("Augmented the user prompt with RAG context.")
                else:
                    self.logger.warning(
                        "No documents retrieved from RAG - context will not be augmented"
                    )
            except Exception as e:
                self.logger.error(f"Error retrieving RAG documents: {e}", exc_info=True)

        trimmed_messages = self.enforce_token_limit(
            current_messages_copy, max_tokens=max_tokens
        )

        # Generate the streaming response
        return groq_client_local.chat.completions.create(
            model=get_default_model(),
            messages=trimmed_messages,
            temperature=0.7,
            max_tokens=max_tokens,
            stream=True,
        )
