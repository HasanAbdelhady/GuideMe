from ..models import CustomUser, Interest

user = CustomUser.objects.first()
interest = Interest.objects.create(name="Test")
user.interests.add(interest)
print(user.interests.all())  # Should show "Test"
