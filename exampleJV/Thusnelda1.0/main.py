import datetime
import time
from decimal import Decimal
from accesoAPI import inicializar_cliente
import csv
import os

# Solicitar meta equity al usuario y validar entrada
try:
    meta_equity = Decimal(input("Ingresa la meta de equity a alcanzar en USDT, NOTA IMPORTANTE: colocar 0 o un numero negativo hara que se ejecute venta de todos los activos a mercado por USDT similar a redButton: "))
    print(f"Meta de equity configurada en: {meta_equity} USDT")
except Exception:
    print("Error: Debes ingresar un número válido. Por favor, reinicia el script.")
    exit()

buscandoMeta = True  # Booleano para controlar el ciclo de búsqueda de la meta

# IMPORTANTE definir correctamente el punto de referencia cronológico de la última compra a mercado no eliminar la siguiente linea comentada
# horaFechaLocalReferencia = datetime.datetime.now()
horaFechaLocalReferencia = datetime.datetime(2025, 3, 22, 10, 45, 57, 183693)

# Parámetros básicos
tiempoEntreEjecucion = 600  # Tiempo de espera tras finalizar un ciclo completo (en segundos)
tiempoEntreCompraPotencial = 3  # Tiempo de espera entre cada símbolo revisado (en segundos)
quoteOrderQtyModulo = Decimal("8")  # Cantidad base de volumen de compra a mercado usualmente en USDT
factor_multiplicacion_porcentual = Decimal("0.99")  # Factor de multiplicación porcentual para decidir compras en formato 0.998

# Informar los parámetros configurados
print("# PARAMETROS BASICOS")
print(f"horaFechaLocalReferenciaInicial = {horaFechaLocalReferencia}")
print(f"tiempoEntreEjecucion = {tiempoEntreEjecucion}")
print(f"tiempoEntreCompraPotencial = {tiempoEntreCompraPotencial}")
print(f"quoteOrderQtyModulo = {quoteOrderQtyModulo}")
print(f"factor_multiplicacion_porcentual = {factor_multiplicacion_porcentual}")

# Leer símbolos desde un archivo externo con validación
def leer_simbolos(archivo):
    if not os.path.exists(archivo):
        print(f"Error: El archivo {archivo} no existe.")
        exit()

    with open(archivo, 'r') as f:
        simbolos = [line.strip() for line in f if line.strip()]

    if not simbolos:
        print(f"Error: El archivo {archivo} está vacío. Por favor, verifica su contenido.")
        exit()

    return simbolos

# Lógica de compra para un símbolo
def procesar_simbolo(client, symbol):
    print(f"Revisando símbolo: {symbol}")
    try:
        compras_mercado = client.get_my_trades(symbol=symbol, fromId=0)
        compras_recientes = [
            c for c in compras_mercado
            if datetime.datetime.fromtimestamp(c["time"] / 1000) > horaFechaLocalReferencia
               and c["isBuyer"]
        ]

        # Si no existen compras recientes, realizar una compra inicial como referencia de precio
        if not compras_recientes:
            print(f"No existen compras recientes para {symbol}. Realizando compra inicial como referencia...")
            try:
                orden_compra_inicial = client.create_order(
                    symbol=symbol,
                    side=client.SIDE_BUY,
                    type=client.ORDER_TYPE_MARKET,
                    quoteOrderQty=quoteOrderQtyModulo,
                )
                print(f"COMPRA inicial realizada para {symbol}. Detalles: {orden_compra_inicial}")
            except Exception as e:
                print(f"Error al realizar la compra inicial para {symbol}: {e}")
            return  # Salir de la función después de la compra inicial

        # Calcular el precio promedio de las últimas 30 compras a mercado (o las existentes)
        precios_compras = [Decimal(c["price"]) for c in compras_recientes][-30:]  # Tomar máximo 30 precios
        precio_promedio = sum(precios_compras) / len(precios_compras)
        print(f"Precio promedio de las últimas compras de {symbol}: {precio_promedio}")

        # Obtener el precio actual del símbolo
        precio_actual = Decimal(client.get_symbol_ticker(symbol=symbol)["price"])
        print(f"Precio actual de {symbol}: {precio_actual}")

        # Comparar el precio actual con el precio promedio ajustado por el factor
        precio_limite = precio_promedio * factor_multiplicacion_porcentual
        print(f"Precio límite calculado para {symbol}: {precio_limite}")

        if precio_actual < precio_limite:
            print(
                f"Precio actual de {symbol}({precio_actual}) está por DEBAJO del límite calculado ({precio_limite}), realizando compra a mercado..."
            )
            try:
                orden_compra = client.create_order(
                    symbol=symbol,
                    side=client.SIDE_BUY,
                    type=client.ORDER_TYPE_MARKET,
                    quoteOrderQty=quoteOrderQtyModulo,
                )
                print(f"COMPRA exitosa de {symbol}. Detalles: {orden_compra}")
            except Exception as e:
                print(f"Error al realizar la compra para {symbol}: {e}")
        else:
            print(
                f"Precio actual de {symbol}({precio_actual}) no cumple las condiciones para realizar compra. ESPERANDO acción del precio..."
            )
    except Exception as e:
        print(f"Error al procesar el símbolo {symbol}: {e}")

# Función para vender todos los activos a mercado por USDT
def vender_todos_a_usdt(client):
    print("Iniciando venta de todos los activos a USDT...")
    try:
        # Obtener balances de la cuenta
        account_info = client.get_account()
        for asset in account_info['balances']:
            free_balance = Decimal(asset['free'])
            if free_balance > 0 and asset['asset'] != "USDT":
                symbol = asset['asset'] + "USDT"
                try:
                    orden_venta = client.order_market_sell(
                        symbol=symbol,
                        quantity=free_balance
                    )
                    print(f"VENTA exitosa de {asset['asset']} al mercado. Detalles: {orden_venta}")
                except Exception as e:
                    print(f"Error al vender {asset['asset']}: {e}")
        print("Proceso de venta completado. Todos los activos han sido convertidos a USDT.")
    except Exception as e:
        print(f"Error durante la venta de activos: {e}")

# Inicio del script
if __name__ == "__main__":
    print(f"HORA DE INICIO DE LA CORRIDA--- Thusnelda2.0 --- {horaFechaLocalReferencia}")
    client = inicializar_cliente()

    # Leer la lista de símbolos desde el archivo
    archivo_simbolos = "simbolos.txt"
    simbolos = leer_simbolos(archivo_simbolos)
    print(f"Símbolos cargados desde {archivo_simbolos}: {simbolos}")

    # Configuración del archivo de registro
    registro_archivo = "registro_equity.csv"
    archivo_creado = False  # Bandera para verificar si se creó el archivo

    if not os.path.exists(registro_archivo):
        # Si el archivo no existe, crear uno nuevo con encabezados
        with open(registro_archivo, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Fecha y hora", "Capital de trabajo (USDT)", "Equity Total excluyendo USDT", "Evento"])
        archivo_creado = True
        print("Archivo de registro creado por primera vez.")

    while buscandoMeta:  # Ejecutar mientras se busca la meta
        for symbol in simbolos:
            procesar_simbolo(client, symbol)
            print(f"ESPERANDO {tiempoEntreCompraPotencial} segundos antes de pasar al siguiente símbolo...")
            time.sleep(tiempoEntreCompraPotencial)

        try:
            # Saldo actual de la cuenta en spot del activo base
            saldo_usdt = Decimal(client.get_asset_balance(asset="USDT")["free"])
            print(f"Capital de trabajo disponible en USDT: {saldo_usdt}")

            # Cálculo del equity total excluyendo USDT
            account_info = client.get_account()
            ticker_prices = client.get_all_tickers()
            asset_prices = {ticker['symbol']: Decimal(ticker['price']) for ticker in ticker_prices}

            equityGeneralActualizado = Decimal(0)

            for asset in account_info['balances']:
                total_balance = Decimal(asset['free']) + Decimal(asset['locked'])
                if total_balance > 0 and asset['asset'] != "USDT":
                    symbol = asset['asset'] + "USDT"
                    if symbol in asset_prices:
                        equity_in_usdt = total_balance * asset_prices[symbol]
                        equityGeneralActualizado += equity_in_usdt

            print(f"Equity actual de la cuenta (sin el USDT de Capital de Trabajo): {equityGeneralActualizado} USDT")

            # Comparar equity con la meta
            if (equityGeneralActualizado + saldo_usdt) >= meta_equity:
                print(f"¡Meta alcanzada! Hora: {datetime.datetime.now()} | Equity: {equityGeneralActualizado} USDT")
                vender_todos_a_usdt(client)
                buscandoMeta = False  # Detener el ciclo principal
                print("El ciclo principal se ha detenido. Todas las operaciones han finalizado.")

            else: print(f"Esperando {tiempoEntreEjecucion} segundos para proximo ciclo")

        except Exception as e:
            print(f"Error al calcular el equity: {e}")

        time.sleep(tiempoEntreEjecucion)
