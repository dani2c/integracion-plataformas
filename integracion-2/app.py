import os
import json
import traceback
from datetime import datetime
from flask import Flask, jsonify, request, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from transbank.common.options import Options as BaseOptions
from transbank.common.integration_type import IntegrationType
from transbank.webpay.webpay_plus.transaction import Transaction

# ======================================================
# CONFIGURACIÓN INICIAL DE FLASK
# ======================================================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///D:\\proyecto\\integracion-2\\inventario_db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ======================================================
# MODELOS DE BASE DE DATOS
# ======================================================
class Sucursal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Integer, nullable=False)

class CasaMatriz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Integer, nullable=False)

class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buy_order = db.Column(db.String(40), unique=True)
    amount = db.Column(db.Float)
    status = db.Column(db.String(20))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    respuesta = db.Column(db.Text)  # Texto JSON serializado

# ======================================================
# CONFIGURACIÓN TRANSBANK (MOCK O REAL)
# ======================================================
class MockTransaction:
    def create(self, buy_order, session_id, amount, return_url):
        # Crear token único con el timestamp
        unique_token = f"mock_token_{buy_order}"
        
        data = request.get_json()
        sucursal_id = data.get('sucursal_id')
        cantidad = int(data.get('cantidad', 0))
        
        print(f"\n--- Mock create ---")
        print(f"Buy Order: {buy_order}")
        print(f"Token: {unique_token}")
        print(f"Sucursal: {sucursal_id}")
        print(f"Cantidad: {cantidad}")
        
        transaccion = Transaccion(
            buy_order=buy_order,
            amount=amount,
            status='INICIADA',
            respuesta=json.dumps({
                "token": unique_token,  # Token único
                "url": url_for('mock_pago_exitoso', _external=True),
                "sucursal_id": sucursal_id,
                "cantidad": cantidad
            }),
            fecha=datetime.now()
        )
        db.session.add(transaccion)
        db.session.commit()
        
        return type('obj', (object,), {
            'token': unique_token,  # Devolver token único
            'url': url_for('mock_pago_exitoso', token=unique_token)  # Pasar token a la página
        })

    
    def commit(self, token):
        print(f"\n--- Mock commit con token: {token} ---")
        
        # Buscar transacción
        transaccion = Transaccion.query.filter(
            Transaccion.respuesta.like(f'%{token}%')
        ).first()
        
        if not transaccion:
            raise Exception(f"Transacción no encontrada con token: {token}")
        
        respuesta = json.loads(transaccion.respuesta)
        sucursal_id = respuesta.get('sucursal_id')
        cantidad = int(respuesta.get('cantidad', 0))
        
        try:
            # Validar stock
            if sucursal_id == "casa_matriz":
                casa_matriz = CasaMatriz.query.first()
                if casa_matriz.cantidad < cantidad:
                    raise Exception(f"Stock insuficiente en Casa Matriz. Disponible: {casa_matriz.cantidad}")
            else:
                sucursal = Sucursal.query.get(int(sucursal_id))
                if not sucursal:
                    raise Exception("Sucursal no existe")
                if sucursal.cantidad < cantidad:
                    raise Exception(f"Stock insuficiente en {sucursal.nombre}. Disponible: {sucursal.cantidad}")
            
            # Descontar stock
            if sucursal_id == "casa_matriz":
                casa_matriz.cantidad -= cantidad
            else:
                sucursal.cantidad -= cantidad
            
            # Marcar como exitosa
            transaccion.status = 'AUTHORIZED'
            transaccion.respuesta = json.dumps({
                "status": "AUTHORIZED",
                "amount": transaccion.amount,
                "authorization_code": "123456",
                "sucursal_id": sucursal_id,
                "cantidad": cantidad,
                "token": token
            })
            db.session.commit()
            
            # Redirigir a éxito
            return type('obj', (object,), {
                'status': 'AUTHORIZED',
                'url': url_for('venta_exitosa', token=token)
            })
            
        except Exception as e:
            # Marcar como fallida
            transaccion.status = 'RECHAZADA'
            transaccion.respuesta = json.dumps({
                "error": str(e),
                "status": "RECHAZADA"
            })
            db.session.commit()
            
            # Redirigir directamente a error
            return type('obj', (object,), {
                'status': 'FAILED',
                'url': url_for('venta_fallida', error=str(e))
            })



# Inicialización de webpay_transaction (IMPORTANTE: debe definirse ANTES de las rutas)
if os.getenv('MOCK_TRANSBANK', 'false').lower() == 'true':
    webpay_transaction = MockTransaction()
    print("\n--- MODO MOCK ACTIVADO ---\n")
else:
    class WebpayOptions(BaseOptions):
        def header_api_key_name(self):
            return "Tbk-Api-Key-Secret"
        def header_commerce_code_name(self):
            return "Tbk-Api-Key-Id"

    webpay_options = WebpayOptions(
        commerce_code="597055555532",
        api_key="579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C", 
        integration_type=IntegrationType.TEST
    )
    webpay_transaction = Transaction(webpay_options)
    print("\n--- MODO REAL ACTIVADO ---\n")

# ======================================================
# CONFIGURACIÓN ADICIONAL
# ======================================================
# Crear tablas si no existen
with app.app_context():
    db.create_all()

# Filtro para deserializar JSON en plantillas
app.jinja_env.filters['fromjson'] = lambda s: json.loads(s)

# ======================================================
# RUTAS DE LA APLICACIÓN
# ======================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/inventario', methods=['GET'])
def get_inventario():
    sucursales = Sucursal.query.all()
    casa_matriz = CasaMatriz.query.first()
    return jsonify({
        "sucursales": [{
            "id": s.id,
            "nombre": s.nombre,
            "cantidad": s.cantidad,
            "precio": s.precio
        } for s in sucursales],
        "casa_matriz": {
            "cantidad": casa_matriz.cantidad,
            "precio": casa_matriz.precio
        } if casa_matriz else {"cantidad": 0, "precio": 0}
    })

@app.route('/api/transformar_usd', methods=['POST'])
def transformar_usd():
    data = request.json
    precio_clp = data.get('precio_clp', 0)
    tasa = 900
    precio_usd = round(precio_clp / tasa, 2)
    return jsonify({"precio_usd": precio_usd})

@app.route('/api/vender', methods=['POST'])
def vender():
    data = request.json
    sucursal_id = data.get('sucursal_id')
    cantidad = data.get('cantidad')

    try:
        if sucursal_id == "casa_matriz":
            casa_matriz = CasaMatriz.query.first()
            if casa_matriz.cantidad < cantidad:
                return jsonify({"error": f"Stock insuficiente en Casa Matriz (disponible: {casa_matriz.cantidad})"}), 400
            casa_matriz.cantidad -= cantidad
        else:
            sucursal = Sucursal.query.get(sucursal_id)
            if not sucursal:
                return jsonify({"error": "Sucursal no encontrada"}), 404
            if sucursal.cantidad < cantidad:
                return jsonify({"error": f"Stock insuficiente en {sucursal.nombre} (disponible: {sucursal.cantidad})"}), 400
            sucursal.cantidad -= cantidad
        
        db.session.commit()
        return jsonify({
            "mensaje": "Venta realizada",
            "stock_restante": casa_matriz.cantidad if sucursal_id == "casa_matriz" else sucursal.cantidad
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



# ======================================================
# RUTAS DE INTEGRACIÓN TRANSBANK
# ======================================================
@app.route('/mock-pago-exitoso')
def mock_pago_exitoso():
    token = request.args.get('token', 'mock_token_123')
    return f'''
    <html>
        <body style="padding: 20px; font-family: Arial;">
            <h2>Procesando Pago...</h2>
            <script>
                // Redirigir automáticamente al endpoint de confirmación
                window.location.href = "/webpay/confirmar?token_ws={token}";
            </script>
        </body>
    </html>
    '''



@app.route('/webpay/iniciar', methods=['POST'])
def webpay_iniciar():
    try:
        data = request.json
        amount = float(data.get('total'))
        sucursal_id = data.get('sucursal_id')
        cantidad = int(data.get('cantidad', 0))
        
        buy_order = str(int(datetime.now().timestamp()))
        session_id = "sesion_" + buy_order
        return_url = url_for('webpay_confirmar', _external=True)

        print(f"\n--- Iniciando transacción ---")
        print(f"Monto: {amount}")
        print(f"Sucursal: {sucursal_id}")
        print(f"Cantidad: {cantidad}")
        
        # Usar la implementación de webpay_transaction
        response = webpay_transaction.create(
            buy_order=buy_order,
            session_id=session_id,
            amount=amount,
            return_url=return_url
        )
        
        return jsonify({
            "url": response.url,
            "token": response.token
        })

    except Exception as e:
        print(f"Error en iniciar: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/webpay/confirmar', methods=['GET'])
def webpay_confirmar():
    try:
        token = request.args.get('token_ws', 'mock_token_123')
        print(f"\n--- Confirmando transacción con token: {token} ---")
        
        response = webpay_transaction.commit(token)
        
        # Si es mock, response.url contiene la ruta correcta (éxito o error)
        if hasattr(response, 'url'):
            return redirect(response.url)
        else:
            return redirect(url_for('venta_exitosa', token=token))

    except Exception as e:
        error_msg = f"Error al confirmar pago: {str(e)}"
        return redirect(url_for('venta_fallida', error=error_msg))



@app.route('/venta-exitosa')
def venta_exitosa():
    token = request.args.get('token')
    transaccion = Transaccion.query.filter(
        Transaccion.respuesta.like(f'%{token}%')
    ).first()
    
    if not transaccion:
        return redirect(url_for('venta_fallida', error="Transacción no encontrada"))
    
    respuesta = json.loads(transaccion.respuesta)
    
    if transaccion.status == 'RECHAZADA':
        return redirect(url_for('venta_fallida', error=respuesta.get('error', 'Error desconocido')))
    
    return render_template('exito.html', transaccion=transaccion, respuesta=respuesta)


@app.route('/venta-fallida')
def venta_fallida():
    error = request.args.get('error', 'Error desconocido')
    return render_template('error.html', error=error)

# ======================================================
# INICIO DE LA APLICACIÓN
# ======================================================
if __name__ == '__main__':
    app.run(debug=True)



