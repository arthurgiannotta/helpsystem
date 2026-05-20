from django.urls import path, re_path
from .views import autenticacao, detalhes, listagem, perfil, perguntar, sair

urlpatterns = [
    path('autenticacao/', autenticacao, name='autenticacao'),
    path('confirmar-email/<uidb64>/<token>/', autenticacao, name='confirmar_email'),
    path('detalhes/<int:id>/', detalhes, name='detalhes'),
    path('listagem/', listagem, name='listagem'),
    path('perfil/', perfil, name='perfil'),
    path('perguntar/', perguntar, name='perguntar'),
    path('perguntar/<int:id>/', perguntar, name='editar_pergunta'),
    path('sair/', sair, name='sair'),
    re_path(r"^.*$", autenticacao),
]
