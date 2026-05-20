from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone

import hashlib
import secrets

class Perfil(models.Model):
    DEPARTAMENTO_CHOICES = [
        ('fin', 'Financeiro'),
        ('jur', 'Jurídico'),
        ('ma', 'Marketing'),
        ('rh', 'Recursos Humanos'),
        ('ti', 'Tecnologia da Informação'),
        ('ou', 'Outros'),
    ]
    departamento = models.CharField(max_length=3, choices=DEPARTAMENTO_CHOICES)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
 
    def __str__(self):
        return f"{self.usuario.username} – {self.departamento}"

class Pergunta(models.Model):
    STATUS_CHOICES = [('aberta', 'Aberta'), ('fechada', 'Fechada'), ('respondida', 'Respondida')]
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='perguntas')
    criado_em = models.DateTimeField(auto_now_add=True)
    editado_em = models.DateTimeField(auto_now=True)
    motivo_reabertura = models.TextField(blank=True, validators=[MinLengthValidator(5)])
    pergunta = models.TextField(validators=[MinLengthValidator(10)])
    reaberta_em = models.DateTimeField(null=True, blank=True)
    reaberta_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberta')
    titulo = models.CharField(max_length=200, validators=[MinLengthValidator(10)])

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo

class Resposta(models.Model):
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='respostas')
    criado_em = models.DateTimeField(auto_now_add=True)
    editado_em = models.DateTimeField(auto_now=True)
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE, related_name='respostas')
    resposta = models.TextField(validators=[MinLengthValidator(10)])

    class Meta:
        ordering = ['criado_em']

    def __str__(self):
        return f"Resposta de {self.autor.first_name} para '{self.pergunta.titulo}'"

class StaffToken(models.Model):
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='staff_tokens_criados')
    descricao = models.CharField(max_length=120, blank=True)
    prefixo = models.CharField(max_length=12, db_index=True, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    usado_em = models.DateTimeField(null=True, blank=True)
    usado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_tokens_usados')

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        status = 'usado' if self.usado_em else 'ativo'
        return f'{self.prefixo}... ({status})'

    @staticmethod
    def codigo():
        return secrets.token_urlsafe(32)

    @classmethod
    def consumir(cls, codigo, usuario):
        token = cls.valido(codigo)
        if not token: return False
        token.ativo = False
        token.usado_em = timezone.now()
        token.usado_por = usuario
        token.save(update_fields=['ativo', 'usado_por', 'usado_em'])
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=['is_staff'])
        return True

    @classmethod
    def criar(cls, criado_por, descricao=''):
        codigo = cls.codigo()
        token = cls.objects.create(
            criado_por=criado_por,
            descricao=descricao,
            token_hash=cls.hashear(codigo),
            prefixo=codigo[:12],
        )
        return token, codigo

    @staticmethod
    def hashear(codigo):
        return hashlib.sha256(codigo.strip().encode()).hexdigest()

    @classmethod
    def valido(cls, codigo):
        if not codigo: return None
        return cls.objects.filter(token_hash=cls.hashear(codigo), ativo=True, usado_em__isnull=True).first()
