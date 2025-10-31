from flask import Response
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sistema_discursos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# Modelos do Banco de Dados
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def criar_dados_iniciais():
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
        
        # Criar alguns discursos de exemplo
        discursos_exemplo = [
            (1, "Você conhece bem a Deus?", "Conhecimento de Deus"),
            (2, "Você vai sobreviver aos últimos dias?", "Sobrevivência"),
            (3, "Você está avançando com a organização unida de Jeová?", "Organização")
        ]
        
        for numero, titulo, tema in discursos_exemplo:
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
    congregacoes = Congregacao.query.filter_by(ativo=True).all()
    return render_template('congregacoes/listar.html', congregacoes=congregacoes)

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
114. Apreço pelas maravilhas da creation de Deus
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
    agenda = AgendaDiscurso.query.order_by(AgendaDiscurso.data_discurso).all()
    return render_template('agenda/listar.html', agenda=agenda, today=date.today())

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
            anfitriao_id=anfitriao_id if anfitriao_id else None
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
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Centro
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
            table = Table(data, colWidths=[1*inch, 0.8*inch, 2.5*inch, 1.5*inch, 1.2*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
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
# NO FINAL DO app.py, SUBSTITUA por:
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        criar_dados_iniciais()
    
    # Para produção, use esta linha:
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)