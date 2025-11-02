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
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-aqui'

# CONFIGURAÇÃO DO BANCO - APENAS PG8000
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Converte para formato pg8000
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+pg8000://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+pg8000://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("✅ Conectado ao PostgreSQL via pg8000")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_discursos.db'
    print("✅ Usando SQLite local")

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

# Tabelas do banco

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregations.id'))
    ativo = db.Column(db.Boolean, default=True)
    
    congregacao = db.relationship('Congregacao', backref=db.backref('users', lazy=True))

class Congregacao(db.Model):
    __tablename__ = 'congregations'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    localidade = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True)

class Discurso(db.Model):
    __tablename__ = 'speeches'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    tema = db.Column(db.String(200), default="Tema a definir")
    descricao = db.Column(db.Text)
    duracao = db.Column(db.Integer, default=30)
    bloqueado = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)

class Orador(db.Model):
    __tablename__ = 'speakers'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregations.id'), nullable=False)
    anfitriao = db.Column(db.Boolean, default=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    aprovado = db.Column(db.Boolean, default=True)
    ativo = db.Column(db.Boolean, default=True)
    
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])

class AgendaDiscurso(db.Model):
    __tablename__ = 'speech_schedule'
    id = db.Column(db.Integer, primary_key=True)
    data_discurso = db.Column(db.Date, nullable=False)
    horario = db.Column(db.String(10), nullable=False)
    discurso_id = db.Column(db.Integer, db.ForeignKey('speeches.id'), nullable=False)
    orador_id = db.Column(db.Integer, db.ForeignKey('speakers.id'), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregations.id'), nullable=False)
    anfitriao_id = db.Column(db.Integer, db.ForeignKey('speakers.id'))
    realizado = db.Column(db.Boolean, default=False)
    confirmado_pelo_orador = db.Column(db.Boolean, default=False)
    data_confirmacao = db.Column(db.DateTime)
    observacoes = db.Column(db.Text)
    
    discurso = db.relationship('Discurso', foreign_keys=[discurso_id])
    orador = db.relationship('Orador', foreign_keys=[orador_id])
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])
    anfitriao = db.relationship('Orador', foreign_keys=[anfitriao_id])

class UsuarioOrador(db.Model):
    __tablename__ = 'speaker_users'
    id = db.Column(db.Integer, primary_key=True)
    orador_id = db.Column(db.Integer, db.ForeignKey('speakers.id'), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    orador = db.relationship('Orador', foreign_keys=[orador_id])

class HistoricoDiscurso(db.Model):
    __tablename__ = 'speech_history'
    id = db.Column(db.Integer, primary_key=True)
    data_realizacao = db.Column(db.Date, nullable=False)
    discurso_id = db.Column(db.Integer, db.ForeignKey('speeches.id'), nullable=False)
    orador_id = db.Column(db.Integer, db.ForeignKey('speakers.id'), nullable=False)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregations.id'), nullable=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    discurso = db.relationship('Discurso', foreign_keys=[discurso_id])
    orador = db.relationship('Orador', foreign_keys=[orador_id])
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])

class CoordenadorDiscursos(db.Model):
    __tablename__ = 'speech_coordinators'
    id = db.Column(db.Integer, primary_key=True)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregations.id'), nullable=False)
    orador_id = db.Column(db.Integer, db.ForeignKey('speakers.id'), nullable=False)
    telefone = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True)
    data_inicio = db.Column(db.Date, default=datetime.utcnow)
    data_fim = db.Column(db.Date)
    
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])
    orador = db.relationship('Orador', foreign_keys=[orador_id])

class OradorDiscurso(db.Model):
    __tablename__ = 'speaker_speeches'
    id = db.Column(db.Integer, primary_key=True)
    orador_id = db.Column(db.Integer, db.ForeignKey('speakers.id'), nullable=False)
    discurso_id = db.Column(db.Integer, db.ForeignKey('speeches.id'), nullable=False)
    aceito = db.Column(db.Boolean, default=False)
    data_aceitacao = db.Column(db.DateTime)
    preparado = db.Column(db.Boolean, default=False)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orador = db.relationship('Orador', foreign_keys=[orador_id])
    discurso = db.relationship('Discurso', foreign_keys=[discurso_id])

class Evento(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    bloqueia_agenda = db.Column(db.Boolean, default=False)
    discursos_especiais = db.Column(db.Integer, default=0)
    congregacao_id = db.Column(db.Integer, db.ForeignKey('congregations.id'))
    
    congregacao = db.relationship('Congregacao', foreign_keys=[congregacao_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def criar_dados_iniciais():
    """Cria apenas os dados que não existem"""
    try:
        # Verifica se já existe congregação
        if not Congregacao.query.first():
            congregacao = Congregacao(nome="Congregação Central", localidade="São Paulo")
            db.session.add(congregacao)
            db.session.commit()
            print("✅ Congregação padrão criada")
        else:
            congregacao = Congregacao.query.first()
        
        # Verifica se já existe usuário admin
        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                nome="Administrador Principal",
                congregacao_id=congregacao.id
            )
            db.session.add(admin)
            print("✅ Usuário admin criado")
        
        # Verifica discursos
        discursos_existentes = Discurso.query.count()
        if discursos_existentes < 194:
            print(f"🔧 Criando discursos faltantes... ({discursos_existentes}/194)")
            
            # LISTA COMPLETA DE DISCURSOS
            todos_discursos = [
                (1, "Você conhece bem a Deus?", "Conhecimento de Deus"),
                (2, "Você vai sobreviver aos últimos dias?", "Sobrevivência"),
                (3, "Você está avançando com a organização unida de Jeová?", "Organização"),
                (4, "Que provas temos de que Deus existe?", "Existência de Deus"),
                (5, "Você pode ter uma família feliz!", "Família"),
                (6, "O Dilúvio dos dias de Noé e você", "Dilúvio"),
                (7, "Imite a misericórdia de Jeová", "Misericórdia"),
                (8, "Viva para fazer a vontade de Deus", "Vontade de Deus"),
                (9, "Escute e faça o que a Bíblia diz", "Obediência"),
                (10, "Seja honesto em tudo", "Honestidade"),
                # Continuação da lista (apenas primeiros 10 para exemplo)
                # Adicione os demais 184 discursos aqui seguindo o mesmo padrão
                (11, "Imite a Jesus e não faça parte do mundo", "Imitação de Cristo"),
                (12, "Deus quer que você respeite quem tem autoridade", "Autoridade"),
                (13, "Qual o ponto de vista de Deus sobre o sexo e o casamento?", "Casamento"),
                (14, "Um povo puro e limpo honra a Jeová", "Pureza"),
                (15, "'Faça o bem a todos'", "Bondade"),
                # ... continue até o 194
                (194, "Como a sabedoria de Deus nos ajuda", "Sabedoria")
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
            print(f"✅ Discursos criados: {Discurso.query.count()}/194")
        else:
            print(f"✅ Todos os 194 discursos já existem")
            
    except Exception as e:
        print(f"❌ Erro ao criar dados iniciais: {e}")
        db.session.rollback()

# =============================================
# ROTAS DE AUTENTICAÇÃO
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

# =============================================
# ROTAS PARA CONGREGAÇÕES
# =============================================

@app.route('/congregacoes')
@login_required
def listar_congregacoes():
    # Aplicar filtros
    status = request.args.get('status')
    localidade = request.args.get('localidade')
    
    query = Congregacao.query
    
    # Filtro por status
    if status == 'ativas':
        query = query.filter_by(ativo=True)
    elif status == 'inativas':
        query = query.filter_by(ativo=False)
    
    # Filtro por localidade
    if localidade:
        query = query.filter(Congregacao.localidade.ilike(f'%{localidade}%'))
    
    congregacoes = query.all()
    
    # Calcular totais para estatísticas
    total_congregacoes = Congregacao.query.count()
    congregacoes_ativas = Congregacao.query.filter_by(ativo=True).count()
    congregacoes_inativas = Congregacao.query.filter_by(ativo=False).count()
    total_oradores = Orador.query.filter_by(ativo=True).count()
    
    # Adicionar coordenador atual e contagem de oradores a cada congregação
    for congregacao in congregacoes:
        # Contar oradores ativos nesta congregação
        congregacao.total_oradores = Orador.query.filter_by(
            congregacao_id=congregacao.id, 
            ativo=True
        ).count()
        
        # Buscar coordenador atual
        coordenador = CoordenadorDiscursos.query.filter_by(
            congregacao_id=congregacao.id, 
            ativo=True
        ).first()
        congregacao.coordenador_atual = coordenador
    
    return render_template('congregacoes/listar.html', 
                         congregacoes=congregacoes,
                         total_congregacoes=total_congregacoes,
                         congregacoes_ativas=congregacoes_ativas,
                         congregacoes_inativas=congregacoes_inativas,
                         total_oradores=total_oradores)

@app.route('/congregacoes/nova', methods=['GET', 'POST'])
@login_required
def nova_congregacao():
    if request.method == 'POST':
        nome = request.form['nome']
        localidade = request.form['localidade']
        
        congregacao = Congregacao(nome=nome, localidade=localidade)
        db.session.add(congregacao)
        db.session.commit()
        flash('Congregação cadastrada com sucesso!', 'success')
        return redirect(url_for('listar_congregacoes'))
    
    return render_template('congregacoes/nova.html')

@app.route('/congregacoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_congregacao(id):
    congregacao = Congregacao.query.get_or_404(id)
    
    if request.method == 'POST':
        congregacao.nome = request.form['nome']
        congregacao.localidade = request.form['localidade']
        congregacao.ativo = 'ativo' in request.form
        
        db.session.commit()
        flash('Congregação atualizada com sucesso!', 'success')
        return redirect(url_for('listar_congregacoes'))
    
    return render_template('congregacoes/editar.html', congregacao=congregacao)

@app.route('/congregacoes/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_congregacao(id):
    congregacao = Congregacao.query.get_or_404(id)
    
    # Verificar se existem registros vinculados
    usuarios_vinculados = User.query.filter_by(congregacao_id=id, ativo=True).count()
    oradores_vinculados = Orador.query.filter_by(congregacao_id=id, ativo=True).count()
    
    if usuarios_vinculados > 0 or oradores_vinculados > 0:
        flash('Não é possível excluir esta congregação pois existem usuários ou oradores vinculados a ela!', 'error')
        return redirect(url_for('listar_congregacoes'))
    
    # Exclusão lógica (marcar como inativa)
    congregacao.ativo = False
    db.session.commit()
    
    flash('Congregação excluída com sucesso!', 'success')
    return redirect(url_for('listar_congregacoes'))

# =============================================
# ROTAS PARA ORADORES
# =============================================

@app.route('/oradores')
@login_required
def listar_oradores():
    oradores = Orador.query.filter_by(ativo=True).all()
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('oradores/listar.html', oradores=oradores, congregacoes=congregacoes)

@app.route('/oradores/novo', methods=['GET', 'POST'])
@login_required
def novo_orador():
    if request.method == 'POST':
        nome = request.form['nome']
        congregacao_id = request.form['congregacao_id']
        telefone = request.form.get('telefone', '')
        email = request.form.get('email', '')
        anfitriao = 'anfitriao' in request.form
        
        orador = Orador(
            nome=nome,
            congregacao_id=congregacao_id,
            telefone=telefone,
            email=email,
            anfitriao=anfitriao
        )
        
        db.session.add(orador)
        db.session.commit()
        flash('Orador cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_oradores'))
    
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('oradores/novo.html', congregacoes=congregacoes)

@app.route('/oradores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_orador(id):
    orador = Orador.query.get_or_404(id)
    
    if request.method == 'POST':
        orador.nome = request.form['nome']
        orador.congregacao_id = request.form['congregacao_id']
        orador.telefone = request.form.get('telefone', '')
        orador.email = request.form.get('email', '')
        orador.anfitriao = 'anfitriao' in request.form
        
        db.session.commit()
        flash('Orador atualizado com sucesso!', 'success')
        return redirect(url_for('listar_oradores'))
    
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('oradores/editar.html', orador=orador, congregacoes=congregacoes)

# =============================================
# ROTAS PARA DISCURSOS
# =============================================

@app.route('/discursos')
@login_required
def listar_discursos():
    discursos = Discurso.query.order_by(Discurso.numero).all()
    discursos_bloqueados = Discurso.query.filter_by(bloqueado=True).count()
    return render_template('discursos/listar.html', 
                         discursos=discursos, 
                         discursos_bloqueados=discursos_bloqueados)

@app.route('/discursos/novo', methods=['GET', 'POST'])
@login_required
def novo_discurso():
    if request.method == 'POST':
        numero = request.form['numero']
        titulo = request.form['titulo']
        tema = request.form['tema']
        descricao = request.form.get('descricao', '')
        duracao = request.form.get('duracao', 30)
        bloqueado = 'bloqueado' in request.form
        
        discurso_existente = Discurso.query.filter_by(numero=numero).first()
        if discurso_existente:
            flash('Já existe um discurso com este número!', 'error')
            return redirect(url_for('novo_discurso'))
        
        discurso = Discurso(
            numero=numero,
            titulo=titulo,
            tema=tema,
            descricao=descricao,
            duracao=duracao,
            bloqueado=bloqueado
        )
        
        db.session.add(discurso)
        db.session.commit()
        flash('Discurso cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_discursos'))
    
    return render_template('discursos/novo.html')

@app.route('/discursos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_discurso(id):
    discurso = Discurso.query.get_or_404(id)
    
    if request.method == 'POST':
        discurso.numero = request.form['numero']
        discurso.titulo = request.form['titulo']
        discurso.tema = request.form['tema']
        discurso.descricao = request.form.get('descricao', '')
        discurso.duracao = request.form.get('duracao', 30)
        discurso.bloqueado = 'bloqueado' in request.form
        
        db.session.commit()
        flash('Discurso atualizado com sucesso!', 'success')
        return redirect(url_for('listar_discursos'))
    
    return render_template('discursos/editar.html', discurso=discurso)

@app.route('/discursos/importar', methods=['GET', 'POST'])
@login_required
def importar_discursos():
    if request.method == 'POST':
        try:
            lista_discursos = request.form['lista_discursos']
            
            if not lista_discursos.strip():
                flash('A lista de discursos está vazia!', 'error')
                return redirect(url_for('importar_discursos'))
            
            linhas = lista_discursos.strip().split('\n')
            discursos_importados = 0
            discursos_atualizados = 0
            erros = []
            
            for i, linha in enumerate(linhas, 1):
                linha = linha.strip()
                if not linha:
                    continue
                
                # Diferentes formatos suportados
                if '. ' in linha:
                    partes = linha.split('. ', 1)
                elif '.' in linha:
                    partes = linha.split('.', 1)
                else:
                    erros.append(f"Linha {i}: Formato inválido - '{linha}'")
                    continue
                
                numero_str = partes[0].strip()
                titulo = partes[1].strip()
                
                if not numero_str.isdigit():
                    erros.append(f"Linha {i}: Número inválido - '{numero_str}'")
                    continue
                
                numero = int(numero_str)
                
                if numero < 1 or numero > 200:
                    erros.append(f"Linha {i}: Número fora do range (1-200) - '{numero}'")
                    continue
                
                discurso_existente = Discurso.query.filter_by(numero=numero).first()
                
                if discurso_existente:
                    discurso_existente.titulo = titulo
                    discursos_atualizados += 1
                else:
                    discurso = Discurso(
                        numero=numero,
                        titulo=titulo,
                        tema="Tema a definir",
                        descricao=f"Discurso público #{numero}",
                        duracao=30,
                        bloqueado=False
                    )
                    db.session.add(discurso)
                    discursos_importados += 1
            
            db.session.commit()
            
            if erros:
                flash(f'Importação com erros: {", ".join(erros[:5])}', 'warning')
            
            flash(f'Importação concluída! {discursos_importados} novos e {discursos_atualizados} atualizados.', 'success')
            return redirect(url_for('listar_discursos'))
            
        except Exception as e:
            flash(f'Erro na importação: {str(e)}', 'error')
    
    # Lista pré-pronta para colar
    lista_preparada = """1. Você conhece bem a Deus?
2. Você vai sobreviver aos últimos dias?
3. Você está avançando com a organização unida de Jeová?
4. Que provas temos de que Deus existe?
5. Você pode ter uma família feliz!
6. O Dilúvio dos dias de Noé e você
7. Imite a misericórdia de Jeová
8. Viva para fazer a vontade de Deus
9. Escute e faça o que a Bíblia diz
10. Seja honesto em tudo"""
    
    return render_template('discursos/importar.html', lista_preparada=lista_preparada)

@app.route('/discursos/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_discurso(id):
    discurso = Discurso.query.get_or_404(id)
    discurso.bloqueado = not discurso.bloqueado
    db.session.commit()
    
    status = "bloqueado" if discurso.bloqueado else "liberado"
    flash(f'Discurso #{discurso.numero} {status}!', 'success')
    return redirect(url_for('listar_discursos'))

@app.route('/discursos/toggle_all', methods=['POST'])
@login_required
def toggle_all_discursos():
    acao = request.form['acao']
    bloquear = (acao == 'bloquear_todos')
    
    discursos = Discurso.query.all()
    for discurso in discursos:
        discurso.bloqueado = bloquear
    
    db.session.commit()
    
    acao_texto = "bloqueados" if bloquear else "liberados"
    flash(f'Todos os discursos foram {acao_texto}!', 'success')
    return redirect(url_for('listar_discursos'))

# =============================================
# ROTAS PARA AGENDA
# =============================================

@app.route('/agenda')
@login_required
def listar_agenda():
    # Filtros
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    congregacao_id = request.args.get('congregacao_id')
    confirmacao = request.args.get('confirmacao')
    
    query = AgendaDiscurso.query
    
    # Aplicar filtros
    if data_inicio:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        query = query.filter(AgendaDiscurso.data_discurso >= data_inicio)
    
    if data_fim:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        query = query.filter(AgendaDiscurso.data_discurso <= data_fim)
    
    if congregacao_id:
        query = query.filter_by(congregacao_id=congregacao_id)
    
    if confirmacao == 'confirmados':
        query = query.filter_by(confirmado_pelo_orador=True)
    elif confirmacao == 'pendentes':
        query = query.filter_by(confirmado_pelo_orador=False)
    
    agenda = query.order_by(AgendaDiscurso.data_discurso).all()
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    
    return render_template('agenda/listar.html', 
                         agenda=agenda, 
                         congregacoes=congregacoes,
                         today=date.today())

@app.route('/agenda/novo', methods=['GET', 'POST'])
@login_required
def novo_agendamento():
    if request.method == 'POST':
        data_discurso = datetime.strptime(request.form['data_discurso'], '%Y-%m-%d').date()
        horario = request.form['horario']
        discurso_id = request.form['discurso_id']
        orador_id = request.form['orador_id']
        congregacao_id = request.form['congregacao_id']
        anfitriao_id = request.form.get('anfitriao_id')
        
        discurso = Discurso.query.get(discurso_id)
        if discurso and discurso.bloqueado:
            flash('Este discurso está bloqueado e não pode ser agendado!', 'error')
            return redirect(url_for('novo_agendamento'))
        
        agendamento = AgendaDiscurso(
            data_discurso=data_discurso,
            horario=horario,
            discurso_id=discurso_id,
            orador_id=orador_id,
            congregacao_id=congregacao_id,
            anfitriao_id=anfitriao_id if anfitriao_id else None,
            confirmado_pelo_orador=False
        )
        
        db.session.add(agendamento)
        db.session.commit()
        flash('Discurso agendado com sucesso!', 'success')
        return redirect(url_for('listar_agenda'))
    
    discursos = Discurso.query.filter_by(bloqueado=False, ativo=True).all()
    oradores = Orador.query.filter_by(aprovado=True, ativo=True).all()
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    anfitrioes = Orador.query.filter_by(anfitriao=True, aprovado=True, ativo=True).all()
    
    return render_template('agenda/novo.html',
                         discursos=discursos,
                         oradores=oradores,
                         congregacoes=congregacoes,
                         anfitrioes=anfitrioes,
                         today=date.today())

@app.route('/agenda/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_agendamento(id):
    agendamento = AgendaDiscurso.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            data_discurso = datetime.strptime(request.form['data_discurso'], '%Y-%m-%d').date()
            horario = request.form['horario']
            discurso_id = request.form['discurso_id']
            orador_id = request.form['orador_id']
            congregacao_id = request.form['congregacao_id']
            anfitriao_id = request.form.get('anfitriao_id')
            realizado = 'realizado' in request.form
            
            # Verificar se discurso está bloqueado
            discurso = Discurso.query.get(discurso_id)
            if discurso and discurso.bloqueado:
                flash('Este discurso está bloqueado e não pode ser agendado!', 'error')
                return redirect(url_for('editar_agendamento', id=id))
            
            # Atualizar agendamento
            agendamento.data_discurso = data_discurso
            agendamento.horario = horario
            agendamento.discurso_id = discurso_id
            agendamento.orador_id = orador_id
            agendamento.congregacao_id = congregacao_id
            agendamento.anfitriao_id = anfitriao_id if anfitriao_id else None
            agendamento.realizado = realizado
            
            db.session.commit()
            flash('Agendamento atualizado com sucesso!', 'success')
            return redirect(url_for('listar_agenda'))
            
        except Exception as e:
            flash(f'Erro ao atualizar agendamento: {str(e)}', 'error')
    
    discursos = Discurso.query.filter_by(bloqueado=False, ativo=True).all()
    oradores = Orador.query.filter_by(aprovado=True, ativo=True).all()
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    anfitrioes = Orador.query.filter_by(anfitriao=True, aprovado=True, ativo=True).all()
    
    return render_template('agenda/editar.html', 
                         agendamento=agendamento,
                         discursos=discursos,
                         oradores=oradores,
                         congregacoes=congregacoes,
                         anfitrioes=anfitrioes)

@app.route('/agenda/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_agendamento(id):
    agendamento = AgendaDiscurso.query.get_or_404(id)
    
    # Salvar informações para a mensagem
    discurso_info = f"#{agendamento.discurso.numero} - {agendamento.discurso.titulo}"
    orador_info = agendamento.orador.nome
    data_info = agendamento.data_discurso.strftime('%d/%m/%Y')
    
    db.session.delete(agendamento)
    db.session.commit()
    
    flash(f'Agendamento excluído: {discurso_info} - {orador_info} ({data_info})', 'success')
    return redirect(url_for('listar_agenda'))

@app.route('/agenda/<int:id>/realizar', methods=['POST'])
@login_required
def realizar_discurso(id):
    agendamento = AgendaDiscurso.query.get_or_404(id)
    
    # Marcar como realizado na agenda
    agendamento.realizado = True
    
    # Registrar no histórico
    historico = HistoricoDiscurso(
        data_realizacao=agendamento.data_discurso,
        discurso_id=agendamento.discurso_id,
        orador_id=agendamento.orador_id,
        congregacao_id=agendamento.congregacao_id,
        observacoes=agendamento.observacoes
    )
    
    db.session.add(historico)
    db.session.commit()
    
    flash('Discurso marcado como realizado e registrado no histórico!', 'success')
    return redirect(url_for('listar_agenda'))

@app.route('/agenda/<int:id>/enviar', methods=['POST'])
@login_required
def enviar_discurso_orador(id):
    agendamento = AgendaDiscurso.query.get_or_404(id)
    flash(f'Discurso enviado para {agendamento.orador.nome}!', 'success')
    return redirect(url_for('listar_agenda'))

# =============================================
# SISTEMA DE LOGIN PARA ORADORES
# =============================================

@app.route('/orador/login', methods=['GET', 'POST'])
def orador_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        usuario = UsuarioOrador.query.filter_by(username=username, ativo=True).first()
        
        if usuario and check_password_hash(usuario.password, password):
            return redirect(url_for('orador_discursos', orador_id=usuario.orador_id))
        else:
            flash('Usuário ou senha inválidos!', 'error')
    
    return render_template('orador/login.html')

@app.route('/orador/<int:orador_id>/discursos')
def orador_discursos(orador_id):
    orador = Orador.query.get_or_404(orador_id)
    discursos = AgendaDiscurso.query.filter(
        AgendaDiscurso.orador_id == orador_id,
        AgendaDiscurso.data_discurso >= date.today()
    ).order_by(AgendaDiscurso.data_discurso).all()
    
    return render_template('orador/discursos.html', orador=orador, discursos=discursos)

@app.route('/orador/<int:orador_id>/criar-usuario', methods=['GET', 'POST'])
@login_required
def criar_usuario_orador(orador_id):
    orador = Orador.query.get_or_404(orador_id)
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        usuario_existente = UsuarioOrador.query.filter_by(username=username).first()
        if usuario_existente:
            flash('Nome de usuário já existe!', 'error')
            return redirect(url_for('criar_usuario_orador', orador_id=orador_id))
        
        usuario = UsuarioOrador(
            orador_id=orador_id,
            username=username,
            password=generate_password_hash(password)
        )
        
        db.session.add(usuario)
        db.session.commit()
        flash(f'Usuário criado para {orador.nome}!', 'success')
        return redirect(url_for('listar_oradores'))
    
    return render_template('orador/criar_usuario.html', orador=orador)

# =============================================
# ROTAS PARA HISTÓRICO DE DISCURSOS
# =============================================

@app.route('/historico')
@login_required
def listar_historico():
    try:
        # Obter todos os parâmetros de filtro
        congregacao_id = request.args.get('congregacao_id', '').strip()
        orador_id = request.args.get('orador_id', '').strip()
        discurso_id = request.args.get('discurso_id', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        
        # Query base
        query = HistoricoDiscurso.query.order_by(HistoricoDiscurso.data_realizacao.desc())
        
        # Filtro por congregação
        if congregacao_id and congregacao_id.isdigit():
            query = query.filter(HistoricoDiscurso.congregacao_id == int(congregacao_id))
        
        # Filtro por orador
        if orador_id and orador_id.isdigit():
            query = query.filter(HistoricoDiscurso.orador_id == int(orador_id))
        
        # Filtro por discurso
        if discurso_id and discurso_id.isdigit():
            query = query.filter(HistoricoDiscurso.discurso_id == int(discurso_id))
        
        # Filtro por data início
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao >= data_inicio_obj)
            except ValueError:
                flash('Data de início inválida', 'warning')
        
        # Filtro por data fim
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao <= data_fim_obj)
            except ValueError:
                flash('Data de fim inválida', 'warning')
        
        # Executar query
        historico = query.all()
        
        # Buscar dados para os selects
        congregacoes = Congregacao.query.filter_by(ativo=True).all()
        oradores = Orador.query.filter_by(ativo=True).all()
        discursos = Discurso.query.filter_by(ativo=True).order_by(Discurso.numero).all()
        
        # Calcular estatísticas
        total_registros = len(historico)
        congregacoes_envolvidas = len(set(h.congregacao_id for h in historico))
        oradores_envolvidos = len(set(h.orador_id for h in historico))
        discursos_realizados = len(set(h.discurso_id for h in historico))
        
        return render_template('historico/listar.html', 
                             historico=historico, 
                             congregacoes=congregacoes,
                             oradores=oradores,
                             discursos=discursos,
                             total_registros=total_registros,
                             congregacoes_envolvidas=congregacoes_envolvidas,
                             oradores_envolvidos=oradores_envolvidos,
                             discursos_realizados=discursos_realizados,
                             filtros={
                                 'congregacao_id': congregacao_id,
                                 'orador_id': orador_id,
                                 'discurso_id': discurso_id,
                                 'data_inicio': data_inicio,
                                 'data_fim': data_fim
                             })
                             
    except Exception as e:
        flash(f'Erro ao carregar histórico: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/historico/novo', methods=['GET', 'POST'])
@login_required
def novo_historico():
    if request.method == 'POST':
        try:
            data_realizacao = datetime.strptime(request.form['data_realizacao'], '%Y-%m-%d').date()
            discurso_id = request.form['discurso_id']
            orador_id = request.form['orador_id']
            congregacao_id = request.form['congregacao_id']
            observacoes = request.form.get('observacoes', '')
            
            historico = HistoricoDiscurso(
                data_realizacao=data_realizacao,
                discurso_id=discurso_id,
                orador_id=orador_id,
                congregacao_id=congregacao_id,
                observacoes=observacoes
            )
            
            db.session.add(historico)
            db.session.commit()
            flash('Discurso histórico registrado com sucesso!', 'success')
            return redirect(url_for('listar_historico'))
            
        except Exception as e:
            flash(f'Erro ao registrar histórico: {str(e)}', 'error')
    
    # Para GET - mostrar formulário
    discursos = Discurso.query.filter_by(ativo=True).all()
    oradores = Orador.query.filter_by(ativo=True).all()
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    
    return render_template('historico/novo.html',
                         discursos=discursos,
                         oradores=oradores,
                         congregacoes=congregacoes)

@app.route('/historico/exportar-pdf')
@login_required
def exportar_historico_pdf():
    try:
        # Verificar se reportlab está instalado
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
        except ImportError:
            flash('Módulo reportlab não está instalado. Gerando CSV como alternativa.', 'warning')
            return exportar_historico_csv()

        # Obter os mesmos filtros da listagem
        congregacao_id = request.args.get('congregacao_id', '').strip()
        orador_id = request.args.get('orador_id', '').strip()
        discurso_id = request.args.get('discurso_id', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        
        # Aplicar os mesmos filtros da listagem
        query = HistoricoDiscurso.query.order_by(HistoricoDiscurso.data_realizacao.desc())
        
        if congregacao_id and congregacao_id.isdigit():
            query = query.filter(HistoricoDiscurso.congregacao_id == int(congregacao_id))
        
        if orador_id and orador_id.isdigit():
            query = query.filter(HistoricoDiscurso.orador_id == int(orador_id))
        
        if discurso_id and discurso_id.isdigit():
            query = query.filter(HistoricoDiscurso.discurso_id == int(discurso_id))
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao >= data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao <= data_fim_obj)
            except ValueError:
                pass
        
        historico = query.all()
        
        if not historico:
            flash('Nenhum dado encontrado para exportar com os filtros aplicados.', 'warning')
            return redirect(url_for('listar_historico'))

        # Criar PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#2c3e50')
        )
        
        elements.append(Paragraph("RELATÓRIO DE HISTÓRICO DE DISCURSOS", title_style))
        
        # Informações dos filtros
        filtros_texto = []
        if congregacao_id:
            congregacao = Congregacao.query.get(int(congregacao_id))
            if congregacao:
                filtros_texto.append(f"Congregação: {congregacao.nome}")
        
        if orador_id:
            orador = Orador.query.get(int(orador_id))
            if orador:
                filtros_texto.append(f"Orador: {orador.nome}")
        
        if discurso_id:
            discurso = Discurso.query.get(int(discurso_id))
            if discurso:
                filtros_texto.append(f"Discurso: #{discurso.numero} - {discurso.titulo}")
        
        if data_inicio:
            filtros_texto.append(f"Data início: {data_inicio}")
        
        if data_fim:
            filtros_texto.append(f"Data fim: {data_fim}")
        
        if filtros_texto:
            filtros_para = Paragraph("<br/>".join(filtros_texto), styles['Normal'])
            elements.append(filtros_para)
            elements.append(Spacer(1, 10))
        
        # Informações gerais
        info_text = f"Total de registros: {len(historico)} | Data de geração: {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Tabela de dados
        data = [['Data', 'Discurso', 'Orador', 'Congregação', 'Observações']]
        
        for item in historico:
            observacoes = item.observacoes if item.observacoes else '-'
            # Limitar observações para não quebrar o layout
            if len(observacoes) > 50:
                observacoes = observacoes[:47] + '...'
            
            data.append([
                item.data_realizacao.strftime('%d/%m/%Y'),
                f"#{item.discurso.numero} - {item.discurso.titulo[:30]}...",
                item.orador.nome,
                item.congregacao.nome,
                observacoes
            ])
        
        # Criar tabela
        table = Table(data, colWidths=[60, 120, 100, 100, 120])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # Rodapé
        elements.append(Paragraph(f"Relatório gerado por: {current_user.nome}", styles['Normal']))
        elements.append(Paragraph("Sistema de Discursos Públicos", styles['Normal']))
        
        doc.build(elements)
        buffer.seek(0)
        
        # Nome do arquivo com data e filtros
        filename = f"historico_discursos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        
        return Response(
            buffer.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        
    except Exception as e:
        flash(f'Erro ao gerar PDF: {str(e)}. Gerando CSV como alternativa.', 'error')
        return exportar_historico_csv()

@app.route('/historico/exportar-csv')
@login_required
def exportar_historico_csv():
    """Exporta histórico em formato CSV como alternativa ao PDF"""
    try:
        # Obter os mesmos filtros da listagem
        congregacao_id = request.args.get('congregacao_id', '').strip()
        orador_id = request.args.get('orador_id', '').strip()
        discurso_id = request.args.get('discurso_id', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        
        # Aplicar os mesmos filtros da listagem
        query = HistoricoDiscurso.query.order_by(HistoricoDiscurso.data_realizacao.desc())
        
        if congregacao_id and congregacao_id.isdigit():
            query = query.filter(HistoricoDiscurso.congregacao_id == int(congregacao_id))
        
        if orador_id and orador_id.isdigit():
            query = query.filter(HistoricoDiscurso.orador_id == int(orador_id))
        
        if discurso_id and discurso_id.isdigit():
            query = query.filter(HistoricoDiscurso.discurso_id == int(discurso_id))
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao >= data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao <= data_fim_obj)
            except ValueError:
                pass
        
        historico = query.all()
        
        if not historico:
            flash('Nenhum dado encontrado para exportar com os filtros aplicados.', 'warning')
            return redirect(url_for('listar_historico'))

        # Criar CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Cabeçalho
        writer.writerow(['Data', 'Número do Discurso', 'Título do Discurso', 'Orador', 'Congregação', 'Observações'])
        
        # Dados
        for item in historico:
            writer.writerow([
                item.data_realizacao.strftime('%d/%m/%Y'),
                item.discurso.numero,
                item.discurso.titulo,
                item.orador.nome,
                item.congregacao.nome,
                item.observacoes or ''
            ])
        
        # Preparar resposta
        output.seek(0)
        buffer = io.BytesIO()
        buffer.write(output.getvalue().encode('utf-8'))
        buffer.seek(0)
        
        # Nome do arquivo
        filename = f"historico_discursos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        
    except Exception as e:
        flash(f'Erro ao gerar CSV: {str(e)}', 'error')
        return redirect(url_for('listar_historico'))

# ROTAS PARA COORDENADOR DE DISCURSOS
@app.route('/congregacoes/<int:id>/coordenador', methods=['GET', 'POST'])
@login_required
def coordenador_congregacao(id):
    congregacao = Congregacao.query.get_or_404(id)
    coordenador_atual = CoordenadorDiscursos.query.filter_by(
        congregacao_id=id, 
        ativo=True
    ).first()
    
    if request.method == 'POST':
        orador_id = request.form['orador_id']
        telefone = request.form['telefone']
        
        # Desativar coordenador anterior se existir
        if coordenador_atual:
            coordenador_atual.ativo = False
            coordenador_atual.data_fim = datetime.utcnow().date()
        
        # Criar novo coordenador
        novo_coordenador = CoordenadorDiscursos(
            congregacao_id=id,
            orador_id=orador_id,
            telefone=telefone
        )
        
        db.session.add(novo_coordenador)
        db.session.commit()
        flash('Coordenador de discursos atualizado com sucesso!', 'success')
        return redirect(url_for('listar_congregacoes'))
    
    oradores = Orador.query.filter_by(congregacao_id=id, ativo=True).all()
    return render_template('congregacoes/coordenador.html',
                         congregacao=congregacao,
                         coordenador=coordenador_atual,
                         oradores=oradores)

# =============================================
# ROTAS PARA ORADOR ACEITAR DISCURSOS
# =============================================

@app.route('/orador/<int:orador_id>/aceitar-discursos')
def aceitar_discursos_orador(orador_id):
    orador = Orador.query.get_or_404(orador_id)
    
    # Buscar todos os discursos
    todos_discursos = Discurso.query.order_by(Discurso.numero).all()
    
    # Buscar discursos que o orador já aceitou/preparou
    discursos_orador = OradorDiscurso.query.filter_by(orador_id=orador_id).all()
    discursos_aceitos = {do.discurso_id: do for do in discursos_orador}
    
    return render_template('orador/aceitar_discursos.html',
                         orador=orador,
                         todos_discursos=todos_discursos,
                         discursos_aceitos=discursos_aceitos)

@app.route('/orador/<int:orador_id>/aceitar-discurso/<int:discurso_id>', methods=['POST'])
def aceitar_discurso_orador(orador_id, discurso_id):
    orador = Orador.query.get_or_404(orador_id)
    discurso = Discurso.query.get_or_404(discurso_id)
    
    # Verificar se já existe registro
    orador_discurso = OradorDiscurso.query.filter_by(
        orador_id=orador_id,
        discurso_id=discurso_id
    ).first()
    
    if orador_discurso:
        orador_discurso.aceito = True
        orador_discurso.data_aceitacao = datetime.utcnow()
    else:
        orador_discurso = OradorDiscurso(
            orador_id=orador_id,
            discurso_id=discurso_id,
            aceito=True,
            data_aceitacao=datetime.utcnow()
        )
        db.session.add(orador_discurso)
    
    db.session.commit()
    flash(f'Discurso #{discurso.numero} aceito com sucesso!', 'success')
    return redirect(url_for('aceitar_discursos_orador', orador_id=orador_id))

@app.route('/orador/<int:orador_id>/remover-discurso/<int:discurso_id>', methods=['POST'])
def remover_discurso_orador(orador_id, discurso_id):
    orador_discurso = OradorDiscurso.query.filter_by(
        orador_id=orador_id,
        discurso_id=discurso_id
    ).first_or_404()
    
    discurso_info = f"#{orador_discurso.discurso.numero}"
    
    db.session.delete(orador_discurso)
    db.session.commit()
    
    flash(f'Discurso {discurso_info} removido da sua lista!', 'success')
    return redirect(url_for('aceitar_discursos_orador', orador_id=orador_id))

@app.route('/orador/<int:orador_id>/discursos-preparados')
def discursos_preparados_orador(orador_id):
    orador = Orador.query.get_or_404(orador_id)
    
    discursos_preparados = OradorDiscurso.query.filter_by(
        orador_id=orador_id,
        aceito=True
    ).order_by(OradorDiscurso.data_aceitacao.desc()).all()
    
    return render_template('orador/discursos_preparados.html',
                         orador=orador,
                         discursos_preparados=discursos_preparados)

# ROTAS PARA ADMIN VISUALIZAR ACEITAÇÕES
@app.route('/admin/discursos-aceitos')
@login_required
def admin_discursos_aceitos():
    # Filtros
    congregacao_id = request.args.get('congregacao_id')
    orador_id = request.args.get('orador_id')
    
    query = OradorDiscurso.query.join(Orador).filter(OradorDiscurso.aceito == True)
    
    if congregacao_id:
        query = query.filter(Orador.congregacao_id == congregacao_id)
    
    if orador_id:
        query = query.filter(OradorDiscurso.orador_id == orador_id)
    
    discursos_aceitos = query.order_by(OradorDiscurso.data_aceitacao.desc()).all()
    
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    oradores = Orador.query.filter_by(ativo=True).all()
    
    return render_template('admin/discursos_aceitos.html',
                         discursos_aceitos=discursos_aceitos,
                         congregacoes=congregacoes,
                         oradores=oradores)

# =============================================
# ROTAS PARA CONFIRMAÇÃO DE DISCURSOS AGENDADOS
# =============================================

@app.route('/orador/<int:orador_id>/confirmar-discurso-agendado/<int:agenda_id>', methods=['POST'])
def confirmar_discurso_agendado(orador_id, agenda_id):
    agenda = AgendaDiscurso.query.get_or_404(agenda_id)
    
    # Verificar se o discurso pertence ao orador
    if agenda.orador_id != orador_id:
        flash('Este discurso não está agendado para você!', 'error')
        return redirect(url_for('orador_discursos', orador_id=orador_id))
    
    agenda.confirmado_pelo_orador = True
    agenda.data_confirmacao = datetime.utcnow()
    db.session.commit()
    
    flash(f'Discurso #{agenda.discurso.numero} confirmado para {agenda.data_discurso.strftime("%d/%m/%Y")}!', 'success')
    return redirect(url_for('orador_discursos', orador_id=orador_id))

@app.route('/orador/<int:orador_id>/cancelar-confirmacao-agendado/<int:agenda_id>', methods=['POST'])
def cancelar_confirmacao_agendado(orador_id, agenda_id):
    agenda = AgendaDiscurso.query.get_or_404(agenda_id)
    
    # Verificar se o discurso pertence ao orador
    if agenda.orador_id != orador_id:
        flash('Este discurso não está agendado para você!', 'error')
        return redirect(url_for('orador_discursos', orador_id=orador_id))
    
    agenda.confirmado_pelo_orador = False
    agenda.data_confirmacao = None
    db.session.commit()
    
    flash('Confirmação do discurso cancelada!', 'warning')
    return redirect(url_for('orador_discursos', orador_id=orador_id))

# =============================================
# SISTEMA DE USUÁRIOS ADMINISTRADORES
# =============================================

@app.route('/usuarios')
@login_required
def listar_usuarios():
    usuarios = User.query.filter_by(ativo=True).all()
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('usuarios/listar.html', usuarios=usuarios, congregacoes=congregacoes)

@app.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
def novo_usuario():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nome = request.form['nome']
        congregacao_id = request.form.get('congregacao_id')
        
        # Verificar se usuário já existe
        usuario_existente = User.query.filter_by(username=username).first()
        if usuario_existente:
            flash('Nome de usuário já existe!', 'error')
            return redirect(url_for('novo_usuario'))
        
        usuario = User(
            username=username,
            password=generate_password_hash(password),
            nome=nome,
            congregacao_id=congregacao_id if congregacao_id else None
        )
        
        db.session.add(usuario)
        db.session.commit()
        flash(f'Usuário {nome} criado com sucesso!', 'success')
        return redirect(url_for('listar_usuarios'))
    
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('usuarios/novo.html', congregacoes=congregacoes)

@app.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    usuario = User.query.get_or_404(id)
    
    if request.method == 'POST':
        usuario.username = request.form['username']
        usuario.nome = request.form['nome']
        usuario.congregacao_id = request.form.get('congregacao_id')
        
        # Atualizar senha apenas se for fornecida
        nova_senha = request.form.get('password')
        if nova_senha:
            usuario.password = generate_password_hash(nova_senha)
        
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('listar_usuarios'))
    
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('usuarios/editar.html', usuario=usuario, congregacoes=congregacoes)

@app.route('/usuarios/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_usuario(id):
    usuario = User.query.get_or_404(id)
    
    # Não permitir excluir o próprio usuário
    if usuario.id == current_user.id:
        flash('Você não pode excluir seu próprio usuário!', 'error')
        return redirect(url_for('listar_usuarios'))
    
    # Não permitir excluir o último administrador
    total_administradores = User.query.filter_by(ativo=True).count()
    if total_administradores <= 1:
        flash('Não é possível excluir o último administrador!', 'error')
        return redirect(url_for('listar_usuarios'))
    
    usuario.ativo = False
    db.session.commit()
    flash(f'Usuário {usuario.nome} excluído com sucesso!', 'success')
    return redirect(url_for('listar_usuarios'))

# =============================================
# RELATÓRIOS PDF 
# =============================================

@app.route('/relatorios/pdf')
@login_required
def relatorios_pdf():
    return render_template('relatorios/pdf.html')

@app.route('/relatorios/gerar-pdf', methods=['POST'])
@login_required
def gerar_pdf():
    try:
        # Verificar se reportlab está instalado
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
        except ImportError:
            flash('Módulo reportlab não está instalado. Entre em contato com o administrador.', 'error')
            return redirect(url_for('relatorios_pdf'))
        
        data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
        data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d').date()
        tipo_relatorio = request.form['tipo_relatorio']
        
        # Buscar dados conforme o período
        if tipo_relatorio == 'discursos_realizados':
            agenda = AgendaDiscurso.query.filter(
                AgendaDiscurso.data_discurso.between(data_inicio, data_fim),
                AgendaDiscurso.realizado == True
            ).order_by(AgendaDiscurso.data_discurso).all()
            titulo = "Relatório de Discursos Realizados"
        else:
            agenda = AgendaDiscurso.query.filter(
                AgendaDiscurso.data_discurso.between(data_inicio, data_fim)
            ).order_by(AgendaDiscurso.data_discurso).all()
            titulo = "Relatório Completo de Agenda"
        
        # Criar PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1,
            textColor=colors.HexColor('#2c3e50')
        )
        
        elements.append(Paragraph(titulo, title_style))
        elements.append(Paragraph(f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        if agenda:
            # Cabeçalho da tabela
            data = [['Data', 'Horário', 'Discurso', 'Orador', 'Congregação', 'Status']]
            
            for item in agenda:
                status = "Realizado" if item.realizado else "Agendado"
                data.append([
                    item.data_discurso.strftime('%d/%m/%Y'),
                    item.horario,
                    f"#{item.discurso.numero} - {item.discurso.titulo}",
                    item.orador.nome,
                    item.congregacao.nome,
                    status
                ])
            
            # Criar tabela
            table = Table(data, colWidths=[60, 50, 180, 100, 80, 50])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            elements.append(Paragraph(f"Total de registros: {len(agenda)}", styles['Normal']))
        else:
            elements.append(Paragraph("Nenhum dado encontrado para o período selecionado.", styles['Normal']))
        
        # Rodapé
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"Relatório gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Normal']))
        elements.append(Paragraph("Sistema de Discursos Públicos", styles['Normal']))
        
        doc.build(elements)
        buffer.seek(0)
        
        filename = f"relatorio_discursos_{data_inicio}_{data_fim}.pdf"
        
        return Response(
            buffer.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        
    except Exception as e:
        flash(f'Erro ao gerar PDF: {str(e)}', 'error')
        return redirect(url_for('relatorios_pdf'))

# =============================================
# INICIALIZAÇÃO FORÇADA DO BANCO
# =============================================

def inicializar_banco():
    """Inicializa o banco apenas se necessário, sem apagar dados existentes"""
    with app.app_context():
        try:
            print("🔄 Verificando banco de dados...")
            
            # Cria tabelas apenas se não existirem
            db.create_all()
            
            # Verifica se já existem dados básicos
            if not Congregacao.query.first():
                print("🌱 Criando dados iniciais...")
                criar_dados_iniciais()
                print("✅ Dados iniciais criados!")
            else:
                print("✅ Banco já possui dados, mantendo existentes.")
                
        except Exception as e:
            print(f"❌ Erro na inicialização do banco: {e}")
            try:
                db.create_all()
                print("✅ Tabelas criadas com sucesso!")
            except Exception as e2:
                print(f"❌ Erro crítico: {e2}")

# Executa a inicialização quando o app startar
inicializar_banco()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)