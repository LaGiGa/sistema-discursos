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

# CONFIGURAÇÃO DO BANCO
database_url = os.environ.get('DATABASE_URL')

if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+pg8000://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+pg8000://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print("✅ Conectado ao PostgreSQL via pg8000")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_discursos.db'
    print("✅ Usando SQLite local")

# Configurações de Email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'seu-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'sua-senha'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MODELOS DO BANCO DE DADOS
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
        if not Congregacao.query.first():
            congregacao = Congregacao(nome="Congregação Central", localidade="São Paulo")
            db.session.add(congregacao)
            db.session.commit()
            print("✅ Congregação padrão criada")
        else:
            congregacao = Congregacao.query.first()
        
        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                nome="Administrador Principal",
                congregacao_id=congregacao.id
            )
            db.session.add(admin)
            print("✅ Usuário admin criado")
        
        discursos_existentes = Discurso.query.count()
        if discursos_existentes < 194:
            print(f"🔧 Criando discursos faltantes... ({discursos_existentes}/194)")
            
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
                (11, "Imite a Jesus e não faça parte do mundo", "Imitação de Cristo"),
                (12, "Deus quer que você respeite quem tem autoridade", "Autoridade"),
                (13, "Qual o ponto de vista de Deus sobre o sexo e o casamento?", "Casamento"),
                (14, "Um povo puro e limpo honra a Jeová", "Pureza"),
                (15, "'Faça o bem a todos'", "Bondade"),
                (16, "Seja cada vez mais amigo de Jeová", "Amizade com Deus"),
                (17, "Glorifique a Deus com tudo o que você tem", "Glorificação"),
                (18, "Faça de Jeová a sua fortaleza", "Fortaleza"),
                (19, "Como você pode saber seu futuro?", "Futuro"),
                (20, "Chegou o tempo de Deus governar o mundo?", "Governo de Deus"),
                (21, "Dê valor ao seu lugar no Reino de Deus", "Reino de Deus"),
                (22, "Você está usando bem o que Jeová lhe dá?", "Mordomia"),
                (23, "A vida tem objetivo", "Objetivo da Vida"),
                (24, "Você encontrou 'uma pérola de grande valor'?", "Valor Espiritual"),
                (25, "Lute contra o espírito do mundo", "Luta Espiritual"),
                (26, "Você é importante para Deus?", "Importância para Deus"),
                (27, "Como construir um casamento feliz", "Casamento Feliz"),
                (28, "Mostre respeito e amor no seu casamento", "Respeito no Casamento"),
                (29, "As responsabilidades e recompensas de ter filhos", "Paternidade"),
                (30, "Como melhorar a comunicação na família", "Comunicação Familiar"),
                (31, "Você tem consciência da sua necessidade espiritual?", "Necessidade Espiritual"),
                (32, "Como lidar com as ansiedades da vida", "Ansiedades"),
                (33, "Quando vai existir verdadeira justiça?", "Justiça"),
                (34, "Você vai ser marcado para sobreviver?", "Sobrevivência"),
                (35, "É possível viver para sempre? O que você precisa fazer?", "Vida Eterna"),
                (36, "Será que a vida é só isso?", "Sentido da Vida"),
                (37, "Obedecer a Deus é mesmo a melhor coisa a fazer?", "Obediência a Deus"),
                (38, "Como você pode sobreviver ao fim do mundo?", "Fim do Mundo"),
                (39, "Jesus Cristo vence o mundo — Como e quando?", "Vitória de Cristo"),
                (40, "O que vai acontecer em breve?", "Eventos Futuros"),
                (41, "Fiquem parados e vejam como Jeová os salvará", "Salvação"),
                (42, "O amor pode vencer o ódio?", "Amor vs Ódio"),
                (43, "Tudo o que Deus nos pede é para o nosso bem", "Bem-estar"),
                (44, "Como os ensinos de Jesus podem ajudar você?", "Ensinos de Jesus"),
                (45, "Continue andando no caminho que leva à vida", "Caminho da Vida"),
                (46, "Fortaleça sua confiança em Jeová", "Confiança"),
                (47, "Discurso Reservado", "Tema Reservado"),
                (48, "Seja leal a Deus mesmo quando for testado", "Lealdade"),
                (49, "Será que um dia a Terra vai ser limpa?", "Terra Limpa"),
                (50, "Como sempre tomar as melhores decisões", "Decisões"),
                (51, "Será que a verdade da Bíblia está mudando a sua vida?", "Verdade Bíblica"),
                (52, "Quem é o seu Deus?", "Deus Verdadeiro"),
                (53, "Você pensa como Deus?", "Pensamento Divino"),
                (54, "Fortaleça sua fé em Deus e em suas promessas", "Fé"),
                (55, "Você está fazendo um bom nome perante Deus?", "Reputação"),
                (56, "Existe um líder em quem você pode confiar?", "Liderança"),
                (57, "Como suportar perseguição", "Perseguição"),
                (58, "Quem são os verdadeiros seguidores de Cristo?", "Seguidores de Cristo"),
                (59, "Discurso Reservado", "Tema Reservado"),
                (60, "Você tem um objetivo na vida?", "Objetivo"),
                (61, "Nas promessas de quem você confia?", "Promessas"),
                (62, "Onde encontrar uma esperança real para o futuro?", "Esperança"),
                (63, "Tem você espírito evangelizador?", "Evangelização"),
                (64, "Você ama os prazeres ou a Deus?", "Amor a Deus"),
                (65, "Como podemos ser pacíficos num mundo cheio de ódio", "Paz"),
                (66, "Você também vai participar na colheita?", "Colheita"),
                (67, "Medite na Bíblia e nas criações de Jeová", "Meditação"),
                (68, "'Continuem a perdoar uns aos outros liberalmente'", "Perdão"),
                (69, "Por que mostrar amor abnegado?", "Amor Abnegado"),
                (70, "Por que Deus merece sua confiança?", "Confiança em Deus"),
                (71, "'Mantenha-se desperto' — Por que e como?", "Vigilância"),
                (72, "O amor identifica os cristãos verdadeiros", "Amor Cristão"),
                (73, "Você tem 'um coração sábio?'", "Sabedoria"),
                (74, "Os olhos de Jeová estão em todo lugar", "Onisciência"),
                (75, "Mostre que você apoia o direito de Jeová governar", "Governo Divino"),
                (76, "Princípios bíblicos — Podem nos ajudar a lidar com os problemas atuais?", "Princípios Bíblicos"),
                (77, "'Sempre mostrem hospitalidade'", "Hospitalidade"),
                (78, "Sirva a Jeová com um coração alegre", "Serviço Alegre"),
                (79, "Você vai escolher ser amigo de Deus?", "Amizade com Deus"),
                (80, "Você baseia a sua esperança na ciência ou na Bíblia?", "Ciência vs Bíblia"),
                (81, "Quem está qualificado para fazer discípulos?", "Discipulado"),
                (82, "Discurso Reservado", "Tema Reservado"),
                (83, "Será que os cristãos precisam obedecer aos Dez Mandamentos?", "Dez Mandamentos"),
                (84, "Escapará do destino deste mundo?", "Destino Mundial"),
                (85, "Boas notícias num mundo violento", "Boas Notícias"),
                (86, "Como orar a Deus e ser ouvido por ele?", "Oração"),
                (87, "Qual é a sua relação com Deus?", "Relação com Deus"),
                (88, "Por que viver de acordo com os padrões da Bíblia?", "Padrões Bíblicos"),
                (89, "Quem tem sede da verdade, venha!", "Verdade"),
                (90, "Faça o máximo para alcançar a verdadeira vida!", "Vida Verdadeira"),
                (91, "A presença do Messias e seu domínio", "Messias"),
                (92, "O papel da religião nos assuntos do mundo", "Religião"),
                (93, "Desastres naturais — Quando vão acabar?", "Desastres Naturais"),
                (94, "A religião verdadeira atende às necessidades da sociedade humana", "Religião Verdadeira"),
                (95, "Não seja enganado pelo ocultismo!", "Ocultismo"),
                (96, "O que vai acontecer com as religiões?", "Futuro das Religiões"),
                (97, "Permaneçamos inculpes em meio a uma geração pervertida", "Inculpabilidade"),
                (98, "'A cena deste mundo está mudando'", "Mudança Mundial"),
                (99, "Por que podemos confiar no que a Bíblia diz?", "Confiança na Bíblia"),
                (100, "Como fazer amizades fortes e verdadeiras", "Amizades"),
                (101, "Jeová é o 'Grandioso Criador'", "Criação"),
                (102, "Preste atenção à 'palavra profética'", "Profecia"),
                (103, "Como você pode ter a verdadeira alegria?", "Alegria"),
                (104, "Pais, vocês estão construindo com materiais à prova de fogo?", "Paternidade Cristã"),
                (105, "Somos consolados em todas as nossas tribulações", "Consolo"),
                (106, "Arruinar a Terra provocará retribuição divina", "Cuidado da Terra"),
                (107, "Você está treinando bem a sua consciência?", "Consciência"),
                (108, "Você pode encarar o futuro com confiança!", "Confiança no Futuro"),
                (109, "O Reino de Deus está próximo", "Reino Próximo"),
                (110, "Deus vem primeiro na vida familiar bem-sucedida", "Deus em Primeiro"),
                (111, "É possível que a humanidade seja completamente curada?", "Cura"),
                (112, "Discurso Reservado", "Tema Reservado"),
                (113, "Jovens — Como vocês podem ter uma vida feliz?", "Juventude"),
                (114, "Aprecio pelas maravilhas da criação de Deus", "Maravilhas da Criação"),
                (115, "Não caia nas armadilhas de Satanás", "Armadilhas de Satanás"),
                (116, "Escolha sabiamente com quem irá associar-se!", "Associações"),
                (117, "Como vencer o mal com o bem", "Bem vs Mal"),
                (118, "Olhemos os jovens do ponto de vista de Jeová", "Juventude e Deus"),
                (119, "Por que é benéfico que os cristãos vivam separados do mundo", "Separação do Mundo"),
                (120, "Por que se submeter à regência de Deus agora", "Submissão a Deus"),
                (121, "Uma família mundial que será salva da destruição", "Família Mundial"),
                (122, "Discurso Reservado", "Tema Reservado"),
                (123, "Discurso Reservado", "Tema Reservado"),
                (124, "Razões para crer que a Bíblia é de autoria divina", "Autoria Divina"),
                (125, "Por que a humanidade precisa de resgate", "Resgate"),
                (126, "Quem se salvará?", "Salvação"),
                (127, "O que acontece quando morremos?", "Morte"),
                (128, "É o inferno um lugar de tormento ardente?", "Inferno"),
                (129, "O que a Bíblia diz sobre a Trindade?", "Trindade"),
                (130, "A Terra permanecerá para sempre", "Terra Eterna"),
                (131, "Discurso Reservado", "Tema Reservado"),
                (132, "Ressurreição — A vitória sobre a morte!", "Ressurreição"),
                (133, "Tem importância o que cremos sobre a nossa origem?", "Origem"),
                (134, "Será que os cristãos precisam guardar o sábado?", "Sábado"),
                (135, "A santidade da vida e do sangue", "Santidade da Vida"),
                (136, "Será que Deus aprova o uso de imagens na adoração?", "Imagens"),
                (137, "Ocorreram realmente os milagres da Bíblia?", "Milagres"),
                (138, "Viva com bom juízo num mundo depravado", "Bom Juízo"),
                (139, "Sabedoria divina num mundo científico", "Sabedoria Divina"),
                (140, "Quem é realmente Jesus Cristo?", "Jesus Cristo"),
                (141, "Quando terão fim os gemidos da criação humana?", "Gemidos da Criação"),
                (142, "Por que refugiar-se em Jeová", "Refúgio em Deus"),
                (143, "Confie no Deus de todo consolo", "Deus de Consolo"),
                (144, "Uma congregação leal sob a liderança de Cristo", "Congregação Leal"),
                (145, "Quem é semelhante a Jeová, nosso Deus?", "Unicidade de Deus"),
                (146, "Use a educação para louvar a Jeová", "Educação"),
                (147, "Confie que Jeová tem o poder para nos salvar", "Poder de Deus"),
                (148, "Você tem o mesmo conceito de Deus sobre a vida?", "Conceito de Vida"),
                (149, "O que significa 'andar com Deus'?", "Andar com Deus"),
                (150, "Este mundo está condenado à destruição?", "Destruição Mundial"),
                (151, "Jeová é 'uma altura protetora' para seu povo", "Proteção Divina"),
                (152, "Armagedom — Por que e quando?", "Armagedom"),
                (153, "Tenha bem em mente o 'atemorizante dia'!", "Dia do Juízo"),
                (154, "O governo humano é pesado na balança", "Governo Humano"),
                (155, "Chegou a hora do julgamento de Babilônia?", "Julgamento de Babilônia"),
                (156, "O Dia do Juízo — Tempo de temor ou de esperança?", "Dia do Juízo"),
                (157, "Como os verdadeiros cristãos adornam o ensino divino", "Ensino Divino"),
                (158, "Seja corajoso e confie em Jeová", "Coragem"),
                (159, "Como encontrar segurança num mundo perigoso", "Segurança"),
                (160, "Mantenha a identidade cristã!", "Identidade Cristã"),
                (161, "Por que Jesus sofreu e morreu?", "Morte de Jesus"),
                (162, "Seja liberto deste mundo em escuridão", "Libertação"),
                (163, "Por que temer o Deus verdadeiro?", "Temor a Deus"),
                (164, "Será que Deus ainda está no controle?", "Controle Divino"),
                (165, "Os valores de quem você preza?", "Valores"),
                (166, "Verdadeira fé — O que é e como mostrar", "Fé Verdadeira"),
                (167, "Ajamos sabiamente num mundo insensato", "Sabedoria Prática"),
                (168, "Você pode sentir-se seguro neste mundo atribulado!", "Segurança"),
                (169, "Por que ser orientado pela Bíblia?", "Orientação Bíblica"),
                (170, "Quem está qualificado para governar a humanidade?", "Governo"),
                (171, "Poderá viver em paz agora — E para sempre!", "Paz Eterna"),
                (172, "Que reputação você tem perante Deus?", "Reputação"),
                (173, "Existe uma religião verdadeira do ponto de vista de Deus?", "Religião Verdadeira"),
                (174, "Quem se qualificará para entrar no novo mundo de Deus?", "Novo Mundo"),
                (175, "O que prova que a Bíblia é autêntica?", "Autenticidade Bíblica"),
                (176, "Quando haverá verdadeira paz e segurança?", "Paz e Segurança"),
                (177, "Onde encontrar ajuda em tempos de aflição?", "Ajuda Divina"),
                (178, "Ande no caminho da integridade", "Integridade"),
                (179, "Rejeite as fantasias do mundo, empenhe-se pelas realidades do Reino", "Realidades do Reino"),
                (180, "A ressurreição — Por que essa esperança deve ser real para você", "Esperança da Ressurreição"),
                (181, "Já é mais tarde do que você imagina?", "Tempo"),
                (182, "O que o Reino de Deus está fazendo por nós agora?", "Reino de Deus"),
                (183, "Desvie seus olhos do que é fútil!", "Futilidade"),
                (184, "A morte é o fim de tudo?", "Morte"),
                (185, "Será que a verdade influencia sua vida?", "Influência da Verdade"),
                (186, "Sirva em união com o povo feliz de Deus", "União"),
                (187, "Por que um Deus amoroso permite a maldade?", "Problema do Mal"),
                (188, "Você confia em Jeová?", "Confiança"),
                (189, "Ande com Deus e receba bênçãos para sempre", "Bênçãos"),
                (190, "Como se cumprirá a promessa de perfeita felicidade familiar", "Felicidade Familiar"),
                (191, "Como o amor e a fé vencem o mundo", "Amor e Fé"),
                (192, "Você está no caminho para a vida eterna?", "Caminho da Vida"),
                (193, "Os problemas de hoje logo serão coisa do passado", "Problemas Temporários"),
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
# ROTAS PARA ADMINISTRAÇÃO DE USUÁRIOS ORADORES
# =============================================

@app.route('/admin/usuarios-oradores')
@login_required
def admin_usuarios_oradores():
    """Lista todos os usuários de oradores para administração"""
    try:
        usuarios_oradores = UsuarioOrador.query.join(Orador).filter(
            UsuarioOrador.ativo == True
        ).order_by(UsuarioOrador.data_criacao.desc()).all()
        
        oradores_sem_usuario = Orador.query.filter(
            Orador.ativo == True,
            ~Orador.id.in_([uo.orador_id for uo in usuarios_oradores])
        ).all()
        
        total_usuarios = len(usuarios_oradores)
        total_oradores_sem_usuario = len(oradores_sem_usuario)
        
        return render_template('admin/usuarios_oradores.html',
                             usuarios_oradores=usuarios_oradores,
                             oradores_sem_usuario=oradores_sem_usuario,
                             total_usuarios=total_usuarios,
                             total_oradores_sem_usuario=total_oradores_sem_usuario)
                             
    except Exception as e:
        flash(f'Erro ao carregar usuários oradores: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/admin/usuarios-oradores/novo', methods=['GET', 'POST'])
@login_required
def admin_novo_usuario_orador():
    """Cria novo usuário para orador"""
    if request.method == 'POST':
        try:
            orador_id = request.form['orador_id']
            username = request.form['username']
            password = request.form['password']
            confirmar_password = request.form['confirmar_password']
            
            if password != confirmar_password:
                flash('As senhas não coincidem!', 'error')
                return redirect(url_for('admin_novo_usuario_orador'))
            
            usuario_existente = UsuarioOrador.query.filter_by(username=username).first()
            if usuario_existente:
                flash('Nome de usuário já existe!', 'error')
                return redirect(url_for('admin_novo_usuario_orador'))
            
            orador_com_usuario = UsuarioOrador.query.filter_by(orador_id=orador_id, ativo=True).first()
            if orador_com_usuario:
                flash('Este orador já possui um usuário cadastrado!', 'error')
                return redirect(url_for('admin_novo_usuario_orador'))
            
            usuario = UsuarioOrador(
                orador_id=orador_id,
                username=username,
                password=generate_password_hash(password)
            )
            
            db.session.add(usuario)
            db.session.commit()
            
            orador = Orador.query.get(orador_id)
            flash(f'Usuário criado com sucesso para {orador.nome}!', 'success')
            return redirect(url_for('admin_usuarios_oradores'))
            
        except Exception as e:
            flash(f'Erro ao criar usuário: {str(e)}', 'error')
    
    oradores_sem_usuario = Orador.query.filter(
        Orador.ativo == True,
        ~Orador.id.in_([uo.orador_id for uo in UsuarioOrador.query.filter_by(ativo=True).all()])
    ).all()
    
    return render_template('admin/novo_usuario_orador.html',
                         oradores_sem_usuario=oradores_sem_usuario)

@app.route('/admin/usuarios-oradores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def admin_editar_usuario_orador(id):
    """Edita usuário de orador"""
    usuario = UsuarioOrador.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            username = request.form['username']
            nova_senha = request.form.get('nova_senha')
            confirmar_senha = request.form.get('confirmar_senha')
            ativo = 'ativo' in request.form
            
            usuario_existente = UsuarioOrador.query.filter(
                UsuarioOrador.username == username,
                UsuarioOrador.id != id
            ).first()
            
            if usuario_existente:
                flash('Nome de usuário já existe!', 'error')
                return redirect(url_for('admin_editar_usuario_orador', id=id))
            
            usuario.username = username
            usuario.ativo = ativo
            
            if nova_senha:
                if nova_senha != confirmar_senha:
                    flash('As senhas não coincidem!', 'error')
                    return redirect(url_for('admin_editar_usuario_orador', id=id))
                
                usuario.password = generate_password_hash(nova_senha)
                flash('Senha atualizada com sucesso!', 'success')
            
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('admin_usuarios_oradores'))
            
        except Exception as e:
            flash(f'Erro ao atualizar usuário: {str(e)}', 'error')
    
    return render_template('admin/editar_usuario_orador.html', usuario=usuario)

@app.route('/admin/usuarios-oradores/<int:id>/resetar-senha', methods=['POST'])
@login_required
def admin_resetar_senha_orador(id):
    """Reseta a senha do usuário orador para um valor padrão"""
    usuario = UsuarioOrador.query.get_or_404(id)
    
    try:
        orador = Orador.query.get(usuario.orador_id)
        senha_padrao = f"{orador.nome.split()[0].lower()}123"
        
        usuario.password = generate_password_hash(senha_padrao)
        db.session.commit()
        
        flash(f'Senha resetada para: {senha_padrao}', 'success')
        return redirect(url_for('admin_usuarios_oradores'))
        
    except Exception as e:
        flash(f'Erro ao resetar senha: {str(e)}', 'error')
        return redirect(url_for('admin_usuarios_oradores'))

@app.route('/admin/usuarios-oradores/<int:id>/excluir', methods=['POST'])
@login_required
def admin_excluir_usuario_orador(id):
    """Exclui usuário de orador (exclusão lógica)"""
    usuario = UsuarioOrador.query.get_or_404(id)
    
    try:
        usuario.ativo = False
        db.session.commit()
        flash('Usuário excluído com sucesso!', 'success')
        return redirect(url_for('admin_usuarios_oradores'))
        
    except Exception as e:
        flash(f'Erro ao excluir usuário: {str(e)}', 'error')
        return redirect(url_for('admin_usuarios_oradores'))

@app.route('/admin/usuarios-oradores/relatorio')
@login_required
def admin_relatorio_usuarios_oradores():
    """Gera relatório de usuários oradores"""
    try:
        usuarios_oradores = UsuarioOrador.query.join(Orador).filter(
            UsuarioOrador.ativo == True
        ).order_by(UsuarioOrador.data_criacao.desc()).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Orador', 'Congregação', 'Usuário', 'Data de Criação', 'Status'])
        
        for usuario in usuarios_oradores:
            writer.writerow([
                usuario.orador.nome,
                usuario.orador.congregacao.nome,
                usuario.username,
                usuario.data_criacao.strftime('%d/%m/%Y'),
                'Ativo' if usuario.ativo else 'Inativo'
            ])
        
        output.seek(0)
        buffer = io.BytesIO()
        buffer.write(output.getvalue().encode('utf-8'))
        buffer.seek(0)
        
        filename = f"relatorio_usuarios_oradores_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'error')
        return redirect(url_for('admin_usuarios_oradores'))

# =============================================
# ROTAS PARA CONGREGAÇÕES
# =============================================

@app.route('/congregacoes')
@login_required
def listar_congregacoes():
    status = request.args.get('status')
    localidade = request.args.get('localidade')
    
    query = Congregacao.query
    
    if status == 'ativas':
        query = query.filter_by(ativo=True)
    elif status == 'inativas':
        query = query.filter_by(ativo=False)
    
    if localidade:
        query = query.filter(Congregacao.localidade.ilike(f'%{localidade}%'))
    
    congregacoes = query.all()
    
    total_congregacoes = Congregacao.query.count()
    congregacoes_ativas = Congregacao.query.filter_by(ativo=True).count()
    congregacoes_inativas = Congregacao.query.filter_by(ativo=False).count()
    total_oradores = Orador.query.filter_by(ativo=True).count()
    
    for congregacao in congregacoes:
        congregacao.total_oradores = Orador.query.filter_by(
            congregacao_id=congregacao.id, 
            ativo=True
        ).count()
        
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
    
    usuarios_vinculados = User.query.filter_by(congregacao_id=id, ativo=True).count()
    oradores_vinculados = Orador.query.filter_by(congregacao_id=id, ativo=True).count()
    
    if usuarios_vinculados > 0 or oradores_vinculados > 0:
        flash('Não é possível excluir esta congregação pois existem usuários ou oradores vinculados a ela!', 'error')
        return redirect(url_for('listar_congregacoes'))
    
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
    
    lista_preparada = """1. Você conhece bem a Deus?
2. Você vai sobreviver aos últimos dias?
3. Você está avançando com a organização unida de Jeová?
4. Que provas temos de que Deus existe?
5. Você pode ter uma família feliz!
6. O Dilúvio dos dias de Noé e você
7. Imite a misericórdia de Jeová
8. Viva para fazer a vontade de Deus
9. Escute e faça o que a Bíblia diz
10. Seja honesto em tudo
11. Imite a Jesus e não faça parte do mundo
12. Deus quer que você respeite quem tem autoridade
13. Qual o ponto de vista de Deus sobre o sexo e o casamento?
14. Um povo puro e limpo honra a Jeová
15. 'Faça o bem a todos'
16. Seja cada vez mais amigo de Jeová
17. Glorifique a Deus com tudo o que você tem
18. Faça de Jeová a sua fortaleza
19. Como você pode saber seu futuro?
20. Chegou o tempo de Deus governar o mundo?
21. Dê valor ao seu lugar no Reino de Deus
22. Você está usando bem o que Jeová lhe dá?
23. A vida tem objetivo
24. Você encontrou "uma pérola de grande valor"?
25. Lute contra o espírito do mundo
26. Você é importante para Deus?
27. Como construir um casamento feliz
28. Mostre respeito e amor no seu casamento
29. As responsabilidades e recompensas de ter filhos
30. Como melhorar a comunicação na família
31. Você tem consciência da sua necessidade espiritual?
32. Como lidar com as ansiedades da vida
33. Quando vai existir verdadeira justiça?
34. Você vai ser marcado para sobreviver?
35. É possível viver para sempre? O que você precisa fazer?
36. Será que a vida é só isso?
37. Obedecer a Deus é mesmo a melhor coisa a fazer?
38. Como você pode sobreviver ao fim do mundo?
39. Jesus Cristo vence o mundo — Como e quando?
40. O que vai acontecer em breve?
41. Fiquem parados e vejam como Jeová os salvará
42. O amor pode vencer o ódio?
43. Tudo o que Deus nos pede é para o nosso bem
44. Como os ensinos de Jesus podem ajudar você?
45. Continue andando no caminho que leva à vida
46. Fortaleça sua confiança em Jeová
47. (Não use.)
48. Seja leal a Deus mesmo quando for testado
49. Será que um dia a Terra vai ser limpa?
50. Como sempre tomar as melhores decisões
51. Será que a verdade da Bíblia está mudando a sua vida?
52. Quem é o seu Deus?
53. Você pensa como Deus?
54. Fortaleça sua fé em Deus e em suas promessas
55. Você está fazendo um bom nome perante Deus?
56. Existe um líder em quem você pode confiar?
57. Como suportar perseguição
58. Quem são os verdadeiros seguidores de Cristo?
59. (Não use.)
60. Você tem um objetivo na vida?
61. Nas promessas de quem você confia?
62. Onde encontrar uma esperança real para o futuro?
63. Tem você espírito evangelizador?
64. Você ama os prazeres ou a Deus?
65. Como podemos ser pacíficos num mundo cheio de ódio
66. Você também vai participar na colheita?
67. Medite na Bíblia e nas criações de Jeová
68. 'Continuem a perdoar uns aos outros liberalmente'
69. Por que mostrar amor abnegado?
70. Por que Deus merece sua confiança?
71. 'Mantenha-se desperto' — Por que e como?
72. O amor identifica os cristãos verdadeiros
73. Você tem "um coração sábio?"
74. Os olhos de Jeová estão em todo lugar
75. Mostre que você apoia o direito de Jeová governar
76. Princípios bíblicos — Podem nos ajudar a lidar com os problemas atuais?
77. "Sempre mostrem hospitalidade"
78. Sirva a Jeová com um coração alegre
79. Você vai escolher ser amigo de Deus?
80. Você baseia a sua esperança na ciência ou na Bíblia?
81. Quem está qualificado para fazer discípulos?
82. (Não use.)
83. Será que os cristãos precisam obedecer aos Dez Mandamentos?
84. Escapará do destino deste mundo?
85. Boas notícias num mundo violento
86. Como orar a Deus e ser ouvido por ele?
87. Qual é a sua relação com Deus?
88. Por que viver de acordo com os padrões da Bíblia?
89. Quem tem sede da verdade, venha!
90. Faça o máximo para alcançar a verdadeira vida!
91. A presença do Messias e seu domínio
92. O papel da religião nos assuntos do mundo
93. Desastres naturais — Quando vão acabar?
94. A religião verdadeira atende às necessidades da sociedade humana
95. Não seja enganado pelo ocultismo!
96. O que vai acontecer com as religiões?
97. Permaneçamos inculpes em meio a uma geração pervertida
98. "A cena deste mundo está mudando"
99. Por que podemos confiar no que a Bíblia diz?
100. Como fazer amizades fortes e verdadeiras
101. Jeová é o "Grandioso Criador"
102. Preste atenção à "palavra profética"
103. Como você pode ter a verdadeira alegria?
104. Pais, vocês estão construindo com materiais à prova de fogo?
105. Somos consolados em todas as nossas tribulações
106. Arruinar a Terra provocará retribuição divina
107. Você está treinando bem a sua consciência?
108. Você pode encarar o futuro com confiança!
109. O Reino de Deus está próximo
110. Deus vem primeiro na vida familiar bem-sucedida
111. É possível que a humanidade seja completamente curada?
112. (Não use.)
113. Jovens — Como vocês podem ter uma vida feliz?
114. Aprecio pelas maravilhas da creation de Deus
115. Não caia nas armadilhas de Satanás
116. Escolha sabiamente com quem irá associar-se!
117. Como vencer o mal com o bem
118. Olhemos os jovens do ponto de vista de Jeová
119. Por que é benéfico que os cristãos vivam separados do mundo
120. Por que se submeter à regência de Deus agora
121. Uma família mundial que será salva da destruição
122. (Não use.)
123. (Não use.)
124. Razões para crer que a Bíblia é de autoria divina
125. Por que a humanidade precisa de resgate
126. Quem se salvará?
127. O que acontece quando morremos?
128. É o inferno um lugar de tormento ardente?
129. O que a Bíblia diz sobre a Trindade?
130. A Terra permanecerá para sempre
131. (Não use.)
132. Ressurreição — A vitória sobre a morte!
133. Tem importância o que cremos sobre a nossa origem?
134. Será que os cristãos precisam guardar o sábado?
135. A santidade da vida e do sangue
136. Será que Deus aprova o uso de imagens na adoração?
137. Ocorreram realmente os milagres da Bíblia?
138. Viva com bom juízo num mundo depravado
139. Sabedoria divina num mundo científico
140. Quem é realmente Jesus Cristo?
141. Quando terão fim os gemidos da criação humana?
142. Por que refugiar-se em Jeová
143. Confie no Deus de todo consolo
144. Uma congregação leal sob a liderança de Cristo
145. Quem é semelhante a Jeová, nosso Deus?
146. Use a educação para louvar a Jeová
147. Confie que Jeová tem o poder para nos salvar
148. Você tem o mesmo conceito de Deus sobre a vida?
149. O que significa "andar com Deus"?
150. Este mundo está condenado à destruição?
151. Jeová é "uma altura protetora" para seu povo
152. Armagedom — Por que e quando?
153. Tenha bem em mente o "atemorizante dia"!
154. O governo humano é pesado na balança
155. Chegou a hora do julgamento de Babilônia?
156. O Dia do Juízo — Tempo de temor ou de esperança?
157. Como os verdadeiros cristãos adornam o ensino divino
158. Seja corajoso e confie em Jeová
159. Como encontrar segurança num mundo perigoso
160. Mantenha a identidade cristã!
161. Por que Jesus sofreu e morreu?
162. Seja liberto deste mundo em escuridão
163. Por que temer o Deus verdadeiro?
164. Será que Deus ainda está no controle?
165. Os valores de quem você preza?
166. Verdadeira fé — O que é e como mostrar
167. Ajamos sabiamente num mundo insensato
168. Você pode sentir-se seguro neste mundo atribulado!
169. Por que ser orientado pela Bíblia?
170. Quem está qualificado para governar a humanidade?
171. Poderá viver em paz agora — E para sempre!
172. Que reputação você tem perante Deus?
173. Existe uma religião verdadeira do ponto de vista de Deus?
174. Quem se qualificará para entrar no novo mundo de Deus?
175. O que prova que a Bíblia é autêntica?
176. Quando haverá verdadeira paz e segurança?
177. Onde encontrar ajuda em tempos de aflição?
178. Ande no caminho da integridade
179. Rejeite as fantasias do mundo, empenhe-se pelas realidades do Reino
180. A ressurreição — Por que essa esperança deve ser real para você
181. Já é mais tarde do que você imagina?
182. O que o Reino de Deus está fazendo por nós now?
183. Desvie seus olhos do que é fútil!
184. A morte é o fim de tudo?
185. Será que a verdade influencia sua vida?
186. Sirva em união com o povo feliz de Deus
187. Por que um Deus amoroso permite a maldade?
188. Você confia em Jeová?
189. Ande com Deus e receba bênçãos para sempre
190. Como se cumprirá a promessa de perfeita felicidade familiar
191. Como o amor e a fé vencem o mundo
192. Você está no caminho para a vida eterna?
193. Os problemas de hoje logo serão coisa do passado
194. Como a sabedoria de Deus nos ajuda"""
    
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
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    congregacao_id = request.args.get('congregacao_id')
    confirmacao = request.args.get('confirmacao')
    
    query = AgendaDiscurso.query
    
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
            
            discurso = Discurso.query.get(discurso_id)
            if discurso and discurso.bloqueado:
                flash('Este discurso está bloqueado e não pode ser agendado!', 'error')
                return redirect(url_for('editar_agendamento', id=id))
            
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
    
    agendamento.realizado = True
    
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

# =============================================
# ROTAS PARA HISTÓRICO DE DISCURSOS
# =============================================

@app.route('/historico')
@login_required
def listar_historico():
    try:
        congregacao_id = request.args.get('congregacao_id', '').strip()
        orador_id = request.args.get('orador_id', '').strip()
        discurso_id = request.args.get('discurso_id', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        
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
                flash('Data de início inválida', 'warning')
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                query = query.filter(HistoricoDiscurso.data_realizacao <= data_fim_obj)
            except ValueError:
                flash('Data de fim inválida', 'warning')
        
        historico = query.all()
        
        congregacoes = Congregacao.query.filter_by(ativo=True).all()
        oradores = Orador.query.filter_by(ativo=True).all()
        discursos = Discurso.query.filter_by(ativo=True).order_by(Discurso.numero).all()
        
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
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
        except ImportError:
            flash('Módulo reportlab não está instalado. Gerando CSV como alternativa.', 'warning')
            return exportar_historico_csv()

        congregacao_id = request.args.get('congregacao_id', '').strip()
        orador_id = request.args.get('orador_id', '').strip()
        discurso_id = request.args.get('discurso_id', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        
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

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30)
        
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#2c3e50')
        )
        
        elements.append(Paragraph("RELATÓRIO DE HISTÓRICO DE DISCURSOS", title_style))
        
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
        
        info_text = f"Total de registros: {len(historico)} | Data de geração: {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        data = [['Data', 'Discurso', 'Orador', 'Congregação', 'Observações']]
        
        for item in historico:
            observacoes = item.observacoes if item.observacoes else '-'
            if len(observacoes) > 50:
                observacoes = observacoes[:47] + '...'
            
            data.append([
                item.data_realizacao.strftime('%d/%m/%Y'),
                f"#{item.discurso.numero} - {item.discurso.titulo[:30]}...",
                item.orador.nome,
                item.congregacao.nome,
                observacoes
            ])
        
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
        
        elements.append(Paragraph(f"Relatório gerado por: {current_user.nome}", styles['Normal']))
        elements.append(Paragraph("Sistema de Discursos Públicos", styles['Normal']))
        
        doc.build(elements)
        buffer.seek(0)
        
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
        congregacao_id = request.args.get('congregacao_id', '').strip()
        orador_id = request.args.get('orador_id', '').strip()
        discurso_id = request.args.get('discurso_id', '').strip()
        data_inicio = request.args.get('data_inicio', '').strip()
        data_fim = request.args.get('data_fim', '').strip()
        
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

        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Data', 'Número do Discurso', 'Título do Discurso', 'Orador', 'Congregação', 'Observações'])
        
        for item in historico:
            writer.writerow([
                item.data_realizacao.strftime('%d/%m/%Y'),
                item.discurso.numero,
                item.discurso.titulo,
                item.orador.nome,
                item.congregacao.nome,
                item.observacoes or ''
            ])
        
        output.seek(0)
        buffer = io.BytesIO()
        buffer.write(output.getvalue().encode('utf-8'))
        buffer.seek(0)
        
        filename = f"historico_discursos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        
    except Exception as e:
        flash(f'Erro ao gerar CSV: {str(e)}', 'error')
        return redirect(url_for('listar_historico'))

# =============================================
# ROTAS PARA COORDENADOR DE DISCURSOS
# =============================================

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
        
        if coordenador_atual:
            coordenador_atual.ativo = False
            coordenador_atual.data_fim = datetime.utcnow().date()
        
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
    
    todos_discursos = Discurso.query.order_by(Discurso.numero).all()
    
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

# =============================================
# ROTAS PARA ADMIN VISUALIZAR ACEITAÇÕES
# =============================================

@app.route('/admin/discursos-aceitos')
@login_required
def admin_discursos_aceitos():
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
# ROTAS PARA SISTEMA DE LOGIN DE ORADORES
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

# =============================================
# ROTAS PARA CONFIRMAÇÃO DE DISCURSOS
# =============================================

@app.route('/orador/<int:orador_id>/confirmar-discurso/<int:agenda_id>', methods=['POST'])
def confirmar_discurso_agendado(orador_id, agenda_id):
    agenda = AgendaDiscurso.query.get_or_404(agenda_id)
    
    if agenda.orador_id != orador_id:
        flash('Este discurso não está agendado para você!', 'error')
        return redirect(url_for('orador_discursos', orador_id=orador_id))
    
    agenda.confirmado_pelo_orador = True
    agenda.data_confirmacao = datetime.utcnow()
    db.session.commit()
    
    flash(f'Discurso #{agenda.discurso.numero} confirmado para {agenda.data_discurso.strftime("%d/%m/%Y")}!', 'success')
    return redirect(url_for('orador_discursos', orador_id=orador_id))

@app.route('/orador/<int:orador_id>/cancelar-confirmacao/<int:agenda_id>', methods=['POST'])
def cancelar_confirmacao_discurso(orador_id, agenda_id):
    agenda = AgendaDiscurso.query.get_or_404(agenda_id)
    
    if agenda.orador_id != orador_id:
        flash('Este discurso não está agendado para você!', 'error')
        return redirect(url_for('orador_discursos', orador_id=orador_id))
    
    agenda.confirmado_pelo_orador = False
    agenda.data_confirmacao = None
    db.session.commit()
    
    flash('Confirmação do discurso cancelada!', 'warning')
    return redirect(url_for('orador_discursos', orador_id=orador_id))

# =============================================
# ROTAS PARA USUÁRIOS ADMINISTRADORES
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
    
    if usuario.id == current_user.id:
        flash('Você não pode excluir seu próprio usuário!', 'error')
        return redirect(url_for('listar_usuarios'))
    
    total_administradores = User.query.filter_by(ativo=True).count()
    if total_administradores <= 1:
        flash('Não é possível excluir o último administrador!', 'error')
        return redirect(url_for('listar_usuarios'))
    
    usuario.ativo = False
    db.session.commit()
    flash(f'Usuário {usuario.nome} excluído com sucesso!', 'success')
    return redirect(url_for('listar_usuarios'))

# =============================================
# INICIALIZAÇÃO DO BANCO
# =============================================

def inicializar_banco():
    """Inicializa o banco apenas se necessário, sem apagar dados existentes"""
    with app.app_context():
        try:
            print("🔄 Verificando banco de dados...")
            
            db.create_all()
            
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

inicializar_banco()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)