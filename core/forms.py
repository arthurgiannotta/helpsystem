from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Perfil, Pergunta, Resposta

class FormCadastro(forms.ModelForm):
    departamento = forms.ChoiceField(choices=Perfil.DEPARTAMENTO_CHOICES)
    password = forms.CharField(label='Senha', widget=forms.PasswordInput(attrs={'placeholder': 'Senha'}))
    password_confirm = forms.CharField(label='Confirmar Senha', widget=forms.PasswordInput(attrs={'placeholder': 'Confirmar Senha'}))
 
    class Meta:
        fields = ['email', 'first_name', 'username']
        model = User
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'E-mail'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Apelido'}),
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
 
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
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
            'pergunta': forms.Textarea(attrs={ 'placeholder': 'Descreva o problema, o que aconteceu, o que já tentou...' }),
            'titulo': forms.TextInput(attrs={'placeholder': 'Título da pergunta'}),
        }

class FormResposta(forms.ModelForm):
    class Meta:
        model = Resposta
        fields = ['resposta']
        widgets = { 'resposta': forms.Textarea(attrs={'placeholder': 'Escreva sua resposta...'}) }
        labels = { 'resposta': 'Resposta' }
