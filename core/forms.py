from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Perfil, Pergunta, Resposta, StaffToken

import unicodedata

class FormAdminUsuario(forms.Form):
    departamento = forms.ChoiceField(choices=Perfil.DEPARTAMENTO_CHOICES)
    first_name = forms.CharField(label='Apelido', min_length=3)
    usuario = forms.IntegerField(widget=forms.HiddenInput)

class FormCadastro(forms.ModelForm):
    departamento = forms.ChoiceField(choices=Perfil.DEPARTAMENTO_CHOICES)
    password = forms.CharField(label='Senha', widget=forms.PasswordInput(attrs={'placeholder': 'Senha'}))
    password_confirm = forms.CharField(label='Confirmar Senha', widget=forms.PasswordInput(attrs={'placeholder': 'Confirmar senha'}))
    staff_token = forms.CharField(
        label='Token de equipe', required=False,
        widget=forms.TextInput(attrs={ 'placeholder': 'Em branco se desconhece', 'autocomplete': 'off' }),
    )

    class Meta:
        fields = ['email', 'first_name', 'username']
        model = User
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'E-mail'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Nome completo'}),
            'username': forms.TextInput(attrs={'placeholder': 'Nome de usuário'}),
        }
 
    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2:
            if p1 == p2:
                try:
                    validate_password(p1)
                except ValidationError as error:
                    self.add_error('password', error)
            else:
                self.add_error('password_confirm', 'Senhas não coincidem.')
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data['email']
        if not email.endswith('@gmail.com'):
            raise forms.ValidationError(
                "O e-mail precisa terminar com @gmail.com"
            )
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email

    def clean_first_name(self):
        first_name = self.cleaned_data['first_name']
        if len(first_name) < 3:
            raise forms.ValidationError("Nome precisa ter ao menos 2 caracteres.")
        return first_name

    def clean_staff_token(self):
        staff_token = self.cleaned_data.get('staff_token', '').strip()
        if staff_token and not StaffToken.valido(staff_token):
            raise forms.ValidationError('Token de equipe inválido ou já utilizado.')
        return staff_token

    def clean_username(self):
        username = self.cleaned_data['username']
        if len(username) < 6:
            raise forms.ValidationError("Usuário precisa ter ao menos 6 caracteres.")
        return username
 
    def save(self, commit=True):
        user = super().save(commit=False)
        #user.is_active = False
        user.set_password(self.cleaned_data['password'])
        if commit:
            staff_token = self.cleaned_data.get('staff_token')
            user.save()
            if staff_token: StaffToken.consumir(staff_token, user)
            Perfil.objects.create(usuario=user, departamento=self.cleaned_data['departamento'])

        return user

class FormLogin(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Nome de usuário'}), label='Usuário')
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Senha'}), label='Senha')

class FormPergunta(forms.ModelForm):
    class Meta:
        fields = ['titulo', 'pergunta']
        labels = { 'pergunta': 'Pergunta', 'titulo': 'Título' }
        model = Pergunta
        widgets = {
            'pergunta': forms.Textarea(attrs={ 'placeholder': 'Descreva o problema, o que aconteceu, o que já tentou...'}),
            'titulo': forms.TextInput(attrs={'placeholder': 'Título da pergunta'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        titulo = cleaned_data.get('titulo')
        if not titulo: return cleaned_data
        normalizar_texto = lambda texto: ''.join(
            c for c in unicodedata.normalize('NFD', texto.lower().strip()) if unicodedata.category(c) != 'Mn'
        )
        titulo_normalizado = normalizar_texto(titulo)
        perguntas = Pergunta.objects.only('id', 'titulo')
        if self.instance.pk:
            perguntas = perguntas.exclude(pk=self.instance.pk)
        for pergunta in perguntas:
            titulo_existente = normalizar_texto(pergunta.titulo)
            if titulo_existente == titulo_normalizado:
                raise forms.ValidationError(f'PERGUNTA_EXISTENTE:{pergunta.id}')
        return cleaned_data

class FormPerfil(forms.ModelForm):
    departamento = forms.ChoiceField(choices=Perfil.DEPARTAMENTO_CHOICES)
    staff_token = forms.CharField(
        label='Token de equipe', required=False,
        widget=forms.TextInput(attrs={ 'placeholder': 'Em branco se desconhece', 'autocomplete': 'off' }),
    )

    class Meta:
        model = User
        fields = ['email', 'first_name']
        labels = { 'email': 'E-mail', 'first_name': 'Apelido' }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'perfil'):
            self.fields['departamento'].initial = self.instance.perfil.departamento

    def clean_email(self):
        email = self.cleaned_data['email']
        if not email.endswith('@gmail.com'):
            raise forms.ValidationError('O e-mail precisa terminar com @gmail.com.')
        usuarios = User.objects.filter(email=email)
        if self.instance.pk:
            usuarios = usuarios.exclude(pk=self.instance.pk)
        if usuarios.exists():
            raise forms.ValidationError('Este e-mail já está em uso.')
        return email

    def clean_first_name(self):
        first_name = self.cleaned_data['first_name']
        if len(first_name) < 3:
            raise forms.ValidationError('Apelido precisa ter ao menos 3 caracteres.')
        return first_name

    def clean_staff_token(self):
        staff_token = self.cleaned_data.get('staff_token', '').strip()
        if not staff_token:
            return staff_token
        if self.instance and self.instance.is_staff:
            raise forms.ValidationError('Você já possui permissão de moderador.')
        if not StaffToken.valido(staff_token):
            raise forms.ValidationError('Token de equipe inválido ou já utilizado.')
        return staff_token

    def save(self, commit=True):
        user = super().save(commit=False)
        #if user.pk and user.email != self.initial.get('email'): user.is_active = False
        if commit:
            staff_token = self.cleaned_data.get('staff_token')
            user.save()
            if staff_token: StaffToken.consumir(staff_token, user)
            Perfil.objects.update_or_create(usuario=user, defaults={ 'departamento': self.cleaned_data['departamento'] })
        return user

class FormResposta(forms.ModelForm):
    class Meta:
        model = Resposta
        fields = ['resposta']
        widgets = { 'resposta': forms.Textarea(attrs={'placeholder': 'Escreva sua resposta...'}) }
        labels = { 'resposta': 'Resposta' }

class FormStaffToken(forms.Form):
    descricao = forms.CharField(
        label='Descrição',
        required=False,
        max_length=120,
        min_length=10,
        widget=forms.TextInput(attrs={
            'placeholder': 'Motivação para criação do token',
        }),
    )
