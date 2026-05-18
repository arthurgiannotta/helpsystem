from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.db import models

class Perfil(models.Model):
    DEPARTAMENTO_CHOICES = [
        ('fin', 'Financeiro'),
        ('jur', 'Jurídico'),
        ('rh', 'Recursos Humanos'),
        ('ti', 'Tecnologia da Informação'),
    ]
    departamento = models.CharField(max_length=3, choices=DEPARTAMENTO_CHOICES)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil', validators=[MinLengthValidator(6)])
 
    def __str__(self):
        return f"{self.usuario.username} – {self.departamento}"

class Pergunta(models.Model):
    STATUS_CHOICES = [('aberta', 'Aberta'), ('fechada', 'Fechada'), ('respondida', 'Respondida')]
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitacoes')
    criado_em = models.DateTimeField(auto_now_add=True)
    pergunta = models.TextField(validators=[MinLengthValidator(10)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberta')
    titulo = models.CharField(max_length=200, validators=[MinLengthValidator(10)])

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo
