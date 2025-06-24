

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


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
    fecha = db.Column(db.DateTime) 
    respuesta = db.Column(db.Text)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.String(255))
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    foto = db.Column(db.LargeBinary, nullable=True)