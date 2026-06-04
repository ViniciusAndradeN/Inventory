from flask import Flask, request, jsonify, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = '123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///estoque.db'

db = SQLAlchemy(app)

# ================= BANCO =================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    senha = db.Column(db.String(100))
    tipo = db.Column(db.String(50))

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_barra = db.Column(db.String(100))
    descricao = db.Column(db.String(200))
    endereco = db.Column(db.String(100))
    posicao_lida = db.Column(db.String(100))
    qtd_lida = db.Column(db.Integer, default=0)
    correto = db.Column(db.Boolean)
    usuario = db.Column(db.String(100))

# ================= INIT =================

with app.app_context():
    db.create_all()

    if not Usuario.query.first():
        db.session.add(Usuario(nome='admin', senha='admin', tipo='admin'))
        db.session.add(Usuario(nome='operador', senha='123', tipo='operador'))
        db.session.commit()

# ================= SEGURANÇA =================

@app.before_request
def proteger():
    if request.endpoint in ['login', 'static']:
        return
    if 'user' not in session:
        return redirect('/login')

def is_admin():
    u = Usuario.query.filter_by(nome=session.get('user')).first()
    return u and u.tipo == 'admin'

# ================= LOGIN =================

@app.route('/login', methods=['GET','POST'])
def login():

    erro = ""

    if request.method == 'POST':

        user = request.form.get('user')
        senha = request.form.get('senha')

        u = Usuario.query.filter_by(nome=user, senha=senha).first()

        if u:
            session['user'] = u.nome
            destino = "/" if u.tipo == 'admin' else "/contagem"

            return """
<html>
<meta http-equiv="refresh" content="1;url=""" + destino + """">

<body style="background:#0f172a;color:white;
display:flex;justify-content:center;align-items:center;
height:100vh;flex-direction:column;">

<img src="https://play-lh.googleusercontent.com/UxaAbeTcK8MZihMW1e6ng_KsrpIKTR9ysiT8zBtWIqPIuY9N9_xAL2Eq0MJvCH3o7A" width="120">

<h3>Entrando...</h3>

</body>
</html>
"""
        else:
            erro = "❌ Usuário ou senha inválidos"

    return """
<html>
<body style="background:linear-gradient(#0f172a,#1e3a8a);
display:flex;justify-content:center;align-items:center;height:100vh;">

<div style="background:white;padding:40px;border-radius:12px;width:320px;text-align:center;">

<img src="https://play-lh.googleusercontent.com/UxaAbeTcK8MZihMW1e6ng_KsrpIKTR9ysiT8zBtWIqPIuY9N9_xAL2Eq0MJvCH3o7A" width="100">

<h2>WMS Inventário</h2>

<form method="POST">
<input name="user" placeholder="Usuário" style="width:100%;padding:10px;margin:10px 0">
<input name="senha" type="password" placeholder="Senha" style="width:100%;padding:10px;margin:10px 0">
<button style="width:100%;padding:10px;background:#1e3a8a;color:white;">Entrar</button>
</form>

<div style="color:red;">""" + erro + """</div>

</div>
</body>
</html>
"""

# ================= LAYOUT =================

def layout(titulo, conteudo):

    return """
<html>
<body style="margin:0;font-family:Segoe UI;display:flex;">

<div style="width:220px;background:#111827;color:white;height:100vh;">

<h2 style="text-align:center;">📦 WMS</h2>

<a href="/" style="display:block;padding:12px;color:white;">📊 Dashboard</a>
<a href="/contagem" style="display:block;padding:12px;color:white;">📦 Coletor</a>
<a href="/upload" style="display:block;padding:12px;color:white;">📤 Importar</a>
<a href="/usuarios" style="display:block;padding:12px;color:white;">👥 Usuários</a>
<a href="/logout" style="display:block;padding:12px;color:white;">🚪 Sair</a>

</div>

<div style="flex:1;">

<div style="background:#1f2937;color:white;padding:15px;
display:flex;justify-content:space-between;">

<a href="#" onclick="history.back()" style="color:white;">⬅️ Voltar</a>

<b>""" + titulo + """</b>

<div>👤 """ + str(session.get('user')) + """</div>

</div>

<div style="padding:30px;">
""" + conteudo + """
</div>

</div>

</body>
</html>
"""

# ================= DASHBOARD =================

@app.route('/')
def home():

    conteudo = """
<h2>📊 Dashboard</h2>

<h3>Total: <span id="total">0</span></h3>
<h3>Lidos: <span id="lidos">0</span></h3>
<h3>OK: <span id="ok">0</span></h3>
<h3>Erro: <span id="erro">0</span></h3>

<h3>👷 Ranking</h3>
<ul id="ranking"></ul>

<br>

<button onclick="window.location='/exportar'"
style="padding:10px;background:#1e3a8a;color:white;">📑 Exportar</button>

<script>
function atualizar(){
fetch('/status')
.then(r=>r.json())
.then(d=>{
total.innerText=d.total;
lidos.innerText=d.lidos;
ok.innerText=d.ok;
erro.innerText=d.erro;

let html="";
for(let u in d.ranking){
html += "<li>"+u+" - "+d.ranking[u]+"</li>";
}
ranking.innerHTML = html;
});
}
setInterval(atualizar,2000);
atualizar();
</script>
"""

    return layout("Dashboard", conteudo)

# ================= STATUS =================

@app.route('/status')
def status():

    total = Item.query.count()
    lidos = Item.query.filter(Item.qtd_lida > 0).count()
    ok = Item.query.filter_by(correto=True).count()
    erro = Item.query.filter_by(correto=False).count()

    ranking = {}

    for i in Item.query.all():
        if i.usuario:
            ranking[i.usuario] = ranking.get(i.usuario, 0) + i.qtd_lida

    return jsonify({
        'total': total,
        'lidos': lidos,
        'ok': ok,
        'erro': erro,
        'ranking': ranking
    })

# ================= UPLOAD =================

@app.route('/upload', methods=['GET','POST'])
def upload():

    if request.method == 'POST':

        file = request.files.get('file')

        try:
            df = pd.read_excel(file, nrows=2000)

            df.columns = df.columns.str.strip().str.lower()

            Item.query.delete()

            dados = [
                Item(
                    codigo_barra=str(r.get('unidade comercial', '')),
                    descricao=r.get('produto', ''),
                    endereco=r.get('posição no depósito', '')
                )
                for r in df.to_dict(orient="records")
            ]

            db.session.bulk_save_objects(dados)
            db.session.commit()

            return "✅ Importado com sucesso"

        except Exception as e:
            return f"❌ Erro no upload: {str(e)}"

    return layout("Upload", """
<input type="file" id="file"><br><br>
<button onclick="env()">Importar</button>

<script>
function env(){
let f=new FormData();
f.append('file',file.files[0]);
fetch('/upload',{method:'POST',body:f})
.then(r=>r.text()).then(alert);
}
</script>
""")
# ================= USUÁRIOS =================

@app.route('/usuarios', methods=['GET','POST'])
def usuarios():

    if request.method == 'POST':
        db.session.add(Usuario(
            nome=request.form.get('nome'),
            senha=request.form.get('senha'),
            tipo=request.form.get('tipo')
        ))
        db.session.commit()

    lista = Usuario.query.all()

    lista_html = ""
    for u in lista:
        lista_html += "<li>"+u.nome+" - "+u.tipo+"</li>"

    return layout("Usuários", """
<form method="POST">
Nome:<br><input name="nome"><br>
Senha:<br><input name="senha"><br>
Tipo:<br>
<select name="tipo">
<option value="operador">Operador</option>
<option value="admin">Admin</option>
</select><br><br>
<button>Criar</button>
</form>

<ul>""" + lista_html + """</ul>
""")

# ================= COLETOR =================

@app.route('/contagem')
def contagem():
    return layout("Coletor", """
    <h2 id="et">Bipar Unidade Comercial</h2>

    <div id="reader" style="width:300px"></div>
    <br>

    <input id="i" placeholder="Ou digite manualmente"
           onkeypress="if(event.key==='Enter')p()">

    <div id="info"></div>

    <script src="https://unpkg.com/html5-qrcode"></script>

    <script>
    let etapa = "produto";
    let item = null;

    function processarCodigo(codigo){
        if(etapa=="produto"){
            fetch('/scan',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({codigo:codigo})
            })
            .then(r=>r.json())
            .then(d=>{
                if(d.ok){
                    item = d;
                    info.innerHTML = d.descricao + "<br>" + d.endereco;

                    etapa = "pos";
                    et.innerText = "Bipar Posição";
                }else{
                    alert("❌ Não encontrado");
                }
            });

        } else {
            fetch('/confirmar',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({
                    id:item.id,
                    posicao:codigo
                })
            })
            .then(r=>r.json())
            .then(d=>{
                alert(d.correta ? "✅ OK" : "❌ ERRO");

                etapa="produto";
                et.innerText="Bipar Unidade Comercial";
                info.innerHTML="";
            });
        }
    }

    function p(){
        processarCodigo(i.value);
        i.value="";
    }

    // ======== LEITOR DE CÂMERA ========
    function iniciarLeitor(){
        const qr = new Html5Qrcode("reader");

        qr.start(
            { facingMode: "environment" }, // câmera traseira
            {
                fps: 10,
                qrbox: 250
            },
            (decodedText) => {
                processarCodigo(decodedText);
            },
            (errorMessage) => {
                // ignora erros de leitura
            }
        );
    }

    iniciarLeitor();
    </script>
    """)

# ================= BACKEND =================

@app.route('/scan', methods=['POST'])
def scan():

    item = Item.query.filter_by(
        codigo_barra=request.json['codigo']
    ).first()

    if not item:
        return jsonify({'ok':False})

    return jsonify({
        'ok':True,
        'id':item.id,
        'descricao':item.descricao,
        'endereco':item.endereco
    })

@app.route('/confirmar', methods=['POST'])
def confirmar():

    item = Item.query.get(request.json['id'])

    pos = request.json['posicao']
    correta = pos == item.endereco

    item.qtd_lida += 1
    item.posicao_lida = pos
    item.correto = correta
    item.usuario = session.get('user')

    db.session.commit()

    return jsonify({'correta':correta})

# ================= EXPORT =================

@app.route('/exportar')
def exportar():

    dados = []

    for i in Item.query.all():
        dados.append({
            'UC': i.codigo_barra,
            'Produto': i.descricao,
            'Posição Sistema': i.endereco,
            'Posição Lida': i.posicao_lida,
            'Status': 'OK' if i.correto else 'ERRO',
            'Usuário': i.usuario
        })

    df = pd.DataFrame(dados)

    buffer = io.BytesIO()
    df.to_excel(buffer,index=False)
    buffer.seek(0)

    return send_file(buffer,
        download_name="inventario.xlsx",
        as_attachment=True)

# ================= LOGOUT =================

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ================= RUN =================

if __name__ == '__main__':
    app.run()
