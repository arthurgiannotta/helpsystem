## Configuração do Projeto

### Pré-requisitos

- Python 3.12+
- pip

---

### Exemplo (Windows)

```bash
git clone https://github.com/arthurgiannotta/helpsystem
cd helpsystem
python -m venv .venv
./.venv/Scripts/activate
pip install -r requirements.txt
python manage.py migrate
```

### Criação de administrador
```bash
python manage.py createsuperuser
```

### Inicialização do servidor

```bash
python manage.py runserver
```

### Execução de testes

```bash
python manage.py test
```
