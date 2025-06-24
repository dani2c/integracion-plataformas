from ssl import Options
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import Options as BaseOptions
from transbank.common.integration_type import IntegrationType



class WebpayOptions(BaseOptions):
    def header_api_key_name(self):
        return "Tbk-Api-Key-Secret"  
    
    def header_commerce_code_name(self):
        return "Tbk-Api-Key-Id"  

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
