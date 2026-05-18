from django.urls import path, re_path
from .views import autenticacao, detalhes, listagem, perguntar

urlpatterns = [
    path('autenticacao/', autenticacao, name='autenticacao'),
    path('detalhes/<int:id>/', detalhes, name='detalhes'),
    path('listagem/', listagem, name='listagem'),
    path('perguntar/', perguntar, name='perguntar'),
    re_path(r"^.*$", autenticacao),
]
