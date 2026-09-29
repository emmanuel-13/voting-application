from django.db import models

# Create your models here.
class Vote(models.Model):
    email = models.EmailField()
    candidate = models.CharField(max_length=20)
    date_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.email} - {self.candidate }"
    
    class Meta:
        verbose_name_plural = "Votes"
        constraints = [
            models.UniqueConstraint(fields=['email'], name='unique_vote')
        ]