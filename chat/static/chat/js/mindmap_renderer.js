// Mindmap Renderer (using D3.js v7)

// Ensure D3.js is loaded
if (!d3) {
    console.error("D3.js library is not loaded. Mindmap rendering will fail.");
}

// Helper to recursively nest children
function buildSubtree(node, allNodes) {
    return {
        name: node.label,
        id: node.id, // Keep id for potential future use
        children: allNodes
            .filter(c => c.parent === node.id)
            .map(c => buildSubtree(c, allNodes))
    };
}

// D3.js rendering logic
function renderMindmap(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error("Mindmap container not found:", containerId);
        return;
    }
    container.innerHTML = ''; // Clear previous content

    if (!d3) {
        // This check is redundant if the top-level check prevents execution,
        // but good for robustness if this function is called directly.
        console.error("D3.js library is not loaded.");
        container.innerHTML = "<p class='text-red-500 p-2'>D3.js library not loaded. Mindmap cannot be rendered.</p>";
        return;
    }

    const width = container.clientWidth || 600; 
    const height = container.clientHeight || 400;

    // Build a D3 hierarchy
    const root = d3.hierarchy({
        name: data.nodes.find(n => n.parent === null)?.label || 'Root',
        id: 'root',
        children: data.nodes.filter(n => n.parent === null)
            .map(parentNode => buildSubtree(parentNode, data.nodes))
    });

    // Compute a tidy layout
    const dx = 30; 
    const dy = width / (root.height + 2); 
    const layout = d3.tree().nodeSize([dx, dy]);
    layout(root);

    let x0 = Infinity;
    let x1 = -x0;
    root.each(d => {
        if (d.x > x1) x1 = d.x;
        if (d.x < x0) x0 = d.x;
    });

    const svg = d3.create("svg")
        .attr("width", width)
        .attr("height", height) 
        .attr("viewBox", [-dy / 2, x0 - dx, width + dy, x1 - x0 + dx * 2]) // Adjusted viewBox
        .attr("style", "max-width: 100%; height: auto; font: 10px sans-serif;");

    const g = svg.append("g");

    g.append("g")
        .attr("fill", "none")
        .attr("stroke", "#555")
        .attr("stroke-opacity", 0.4)
        .attr("stroke-width", 1.5)
        .selectAll("path")
        .data(root.links())
        .join("path")
        .attr("d", d3.linkHorizontal()
            .x(d => d.y)
            .y(d => d.x));

    const node = g.append("g")
        .attr("stroke-linejoin", "round")
        .attr("stroke-width", 3)
        .selectAll("g")
        .data(root.descendants())
        .join("g")
        .attr("transform", d => `translate(${d.y},${d.x})`);

    node.append("circle")
        .attr("fill", d => d.children ? "#555" : "#999")
        .attr("r", 4);

    node.append("text")
        .attr("dy", "0.31em")
        .attr("x", d => d.children ? -8 : 8)
        .attr("text-anchor", d => d.children ? "end" : "start")
        .text(d => d.data.name)
        .clone(true).lower()
        .attr("stroke", "white");

    svg.call(d3.zoom().scaleExtent([0.5, 5]).on("zoom", (event) => {
        g.attr("transform", event.transform);
    }));

    container.appendChild(svg.node());
} 