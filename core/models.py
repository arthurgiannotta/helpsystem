from django.contrib.auth.models import User
from django.db import models

class Pergunta(models.Model):
    STATUS_CHOICES = [('aberta', 'Aberta'), ('fechada', 'Fechada'), ('respondida', 'Respondida')]
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitacoes')
    criado_em = models.DateTimeField(auto_now_add=True)
    pergunta = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberta')
    titulo = models.CharField(max_length=200)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo
