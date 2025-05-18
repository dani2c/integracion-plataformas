from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import Options as BaseOptions
from transbank.common.integration_type import IntegrationType


# 1. Crea una subclase que implemente los métodos abstractos
class WebpayOptions(BaseOptions):
    def header_api_key_name(self):
        return "Tbk-Api-Key-Secret"  # Nombre del header para la API Key
    
    def header_commerce_code_name(self):
        return "Tbk-Api-Key-Id"  # Nombre del header para el código de comercio

options = Options(
    commerce_code="597055555532",
    api_key="579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C",
    integration_type=IntegrationType.TEST
)

try:
    response = Transaction(options).create(
        buy_order="TEST_123",
        session_id="sesion_123",
        amount=1000,
        return_url="http://localhost:5000/webpay/confirmar"
    )
    print("Respuesta de Transbank:", response)
except Exception as e:
    print("Error en Transbank:", str(e))
