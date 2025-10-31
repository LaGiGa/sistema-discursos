from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-aqui'

# =============================================
# CONFIGURAÇÃO DO BANCO DE DADOS - POSTGRESQL
# =============================================
# Configuração do Banco de Dados
import os

if os.environ.get('RENDER'):
    # PostgreSQL no Render com pg8000
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Converte para formato do pg8000 se necessário
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql+pg8000://', 1)
        elif database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+pg8000://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        print("✅ Usando PostgreSQL no Render com pg8000")
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_discursos.db'
        print("⚠️  DATABASE_URL não encontrado, usando SQLite")
else:
    # SQLite local para desenvolvimento
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_discursos.db'
    print("✅ Usando SQLite local")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True
}

# Configurações de Email (opcional)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'seu-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'sua-senha'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# =============================================
# MODELOS DO BANCO DE DADOS (MANTIDOS)
# =============================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregacao.id'))
    ativo = db.Column(db.Boolean, default=True)

class Congregacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    localidade = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    usuarios = db.relationship('User', backref='congregacao', lazy=True)
    oradores = db.relationship('Orador', backref='congregacao', lazy=True)
    coordenador_discursos = db.relationship('CoordenadorDiscursos', backref='congregacao', lazy=True)

class Discurso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    tema = db.Column(db.String(200), default="Tema a definir")
    descricao = db.Column(db.Text)
    duracao = db.Column(db.Integer, default=30)
    bloqueado = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)

class Orador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregacao.id'), nullable=False)
    anfitriao = db.Column(db.Boolean, default=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    aprovado = db.Column(db.Boolean, default=True)
    ativo = db.Column(db.Boolean, default=True)

class Evento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    bloqueia_agenda = db.Column(db.Boolean, default=False)
    discursos_especiais = db.Column(db.Integer, default=0)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregacao.id'))

class AgendaDiscurso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_discurso = db.Column(db.Date, nullable=False)
    horario = db.Column(db.String(10), nullable=False)
    discurso_id = db.Column(db.Integer, db.ForeignKey('discurso.id'), nullable=False)
    orador_id = db.Column(db.Integer, db.ForeignKey('orador.id'), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregacao.id'), nullable=False)
    anfitriao_id = db.Column(db.Integer, db.ForeignKey('orador.id'))
    realizado = db.Column(db.Boolean, default=False)
    observacoes = db.Column(db.Text)
    
    discurso = db.relationship('Discurso', foreign_keys=[discurso_id])
    orador = db.relationship('Orador', foreign_keys=[orador_id])
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])
    anfitriao = db.relationship('Orador', foreign_keys=[anfitriao_id])

class UsuarioOrador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orador_id = db.Column(db.Integer, db.ForeignKey('orador.id'), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    orador = db.relationship('Orador', backref='usuario')

# NOVOS MODELOS ADICIONADOS
class HistoricoDiscurso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_realizacao = db.Column(db.Date, nullable=False)
    discurso_id = db.Column(db.Integer, db.ForeignKey('discurso.id'), nullable=False)
    orador_id = db.Column(db.Integer, db.ForeignKey('orador.id'), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregacao.id'), nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    discurso = db.relationship('Discurso', foreign_keys=[discurso_id])
    orador = db.relationship('Orador', foreign_keys=[orador_id])
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])

class CoordenadorDiscursos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregacao.id'), nullable=False)
    orador_id = db.Column(db.Integer, db.ForeignKey('orador.id'), nullable=False)
    telefone = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, default=datetime.utcnow)
    data_fim = db.Column(db.Date)
    
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])
    orador = db.relationship('Orador', foreign_keys=[orador_id])

class OradorDiscurso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orador_id = db.Column(db.Integer, db.ForeignKey('orador.id'), nullable=False)
    discurso_id = db.Column(db.Integer, db.ForeignKey('discurso.id'), nullable=False)
    aceito = db.Column(db.Boolean, default=False)
    data_aceitacao = db.Column(db.DateTime)
    preparado = db.Column(db.Boolean, default=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orador = db.relationship('Orador', foreign_keys=[orador_id])
    discurso = db.relationship('Discurso', foreign_keys=[discurso_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def criar_dados_iniciais():
    """Cria dados iniciais apenas se não existirem"""
    try:
        # Verifica se já existem congregações
        if not Congregacao.query.first():
            congregacao = Congregacao(nome="Congregação Central", localidade="São Paulo")
            db.session.add(congregacao)
            db.session.commit()
            
            # Criar usuário admin padrão
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                nome="Administrador Principal",
                congregacao_id=congregacao.id
            )
            db.session.add(admin)
            
            # Criar TODOS os 194 discursos
            todos_discursos = [
                (1, "Você conhece bem a Deus?", "Conhecimento de Deus"),
                (2, "Você vai sobreviver aos últimos dias?", "Sobrevivência"),
                # ... (todos os 194 discursos que você já tem)
                (194, "Como a sabedoria de Deus nos ajuda", "Sabedoria de Deus")
            ]
            
            for numero, titulo, tema in todos_discursos:
                discurso_existente = Discurso.query.filter_by(numero=numero).first()
                if not discurso_existente:
                    discurso = Discurso(
                        numero=numero,
                        titulo=titulo,
                        tema=tema,
                        descricao=f"Discurso público #{numero}",
                        duracao=30,
                        bloqueado=False
                    )
                    db.session.add(discurso)
            
            db.session.commit()
            print("✅ Dados iniciais criados com sucesso!")
        else:
            print("✅ Dados já existem, pulando criação inicial")
            
    except Exception as e:
        print(f"❌ Erro ao criar dados iniciais: {e}")
        db.session.rollback()

# =============================================
# ROTAS (MANTIDAS - MESMO CÓDIGO ANTERIOR)
# =============================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, ativo=True).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_oradores = Orador.query.filter_by(ativo=True).count()
    total_discursos = AgendaDiscurso.query.count()
    discursos_este_mes = AgendaDiscurso.query.filter(
        AgendaDiscurso.data_discurso >= date(date.today().year, date.today().month, 1)
    ).count()
    congregacoes_count = Congregacao.query.filter_by(ativo=True).count()
    total_discursos_cadastrados = Discurso.query.count()
    
    proximos_discursos = AgendaDiscurso.query.filter(
        AgendaDiscurso.data_discurso >= date.today()
    ).order_by(AgendaDiscurso.data_discurso).limit(5).all()
    
    return render_template('dashboard.html',
                         total_oradores=total_oradores,
                         total_discursos=total_discursos,
                         discursos_este_mes=discursos_este_mes,
                         congregacoes_count=congregacoes_count,
                         total_discursos_cadastrados=total_discursos_cadastrados,
                         proximos_discursos=proximos_discursos)

# ... (TODAS AS OUTRAS ROTAS PERMANECEM EXATAMENTE IGUAIS)
# [Todo o resto do código das rotas que eu te enviei anteriormente]

if __name__ == '__main__':
    with app.app_context():
        try:
            print("🔄 Criando tabelas no banco de dados...")
            db.create_all()
            print("✅ Tabelas criadas com sucesso!")
            
            print("🔄 Verificando dados iniciais...")
            criar_dados_iniciais()
            
        except Exception as e:
            print(f"❌ Erro durante inicialização: {e}")
    
    # Para produção
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)