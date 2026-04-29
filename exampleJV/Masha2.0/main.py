from accesoAPI import inicializar_cliente
from decimal import Decimal
from solicitarOHLCAPI import obtener_datos_ohlc
from obtenerPosicionOrdenSellLimit import posicionOrdenLimit
from compraMarket import compraMarket
from solicitaBalancesAPI import obtener_balances
from actualizarOrdenSellLimitDCA import actualizarOrdenSellLimit
import time
import traceback
import csv
from datetime import datetime

# Inicializa el cliente de la API de Binance
client = inicializar_cliente()

# Define el símbolo de trading y los activos base y de cotización
symbol = "BTCUSDT"
baseAsset = "BTC"
quoteAsset = "USDT"

# Define el balance mínimo libre requerido para operar
balanceQuoteAssetLibreMinOperar = Decimal(6.0)

# Precisión decimal para los cálculos
prec = 8

# Define el volumen de compra y el factor de beneficio porcentual
volumenCompra = Decimal(0.001)
puntosFactorBeneficioPorcentual = Decimal(0.01)

# Configuración de los timeframes y márgenes para las señales de compra
timeFrameW = "1w"
numPeriodosTimeframeW = 2
numPeriodosMMW = 2
puntosMargenLowW = Decimal(0.03)

timeFrameh = "1h"
numPeriodosTimeFrameh = 2
numPeriodosMMh = 2
puntosMargenLowh = Decimal(0.003)

# Tiempo de espera entre ejecuciones del bucle principal (en segundos)
tiempoEntreEjecucion = 300

# Nombre del archivo CSV
csv_filename = 'trading_bot_stats.csv'

# Escribe los encabezados del archivo CSV si no existe
with open(csv_filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow([
        'Fecha y Hora', 'closeActualw', 'closeActualh', 'precioMMw', 'precioMMh',
        'ultimo_lowW', 'ultimo_lowh', 'balanceQuoteAssetLibre', 'precioUltimaCompraMarket',
        'volumenUltimaCompraMarket', 'costoTotalUltimaCompraMarket', 'nuevoPrecioDCAPosicion',
        'precioDCAConBeneficio'
    ])

#Declarando variables solo para la toma estadistica se pueden eliminar...
precioUltimaCompraMarket = None
nuevoPrecioDCAPosicion = None
precioDCAConBeneficio = None

# Bucle principal que se ejecuta continuamente
while True:
    if __name__ == '__main__':
        try:
            # Obtiene los datos de la orden limit que representa la posición actual
            DCAPrecioPosicion, DCAVolumenPosicion, DCAcostoTotalPosicion = posicionOrdenLimit(symbol)

            # Obtiene la señal de compra del timeframe semanal (W)
            precioMMw, ultimo_lowW, closeActualw = obtener_datos_ohlc(symbol, numPeriodosTimeframeW, timeFrameW, numPeriodosMMW)

            # Obtiene la señal de compra del timeframe horario (H)
            precioMMh, ultimo_lowh, closeActualh = obtener_datos_ohlc(symbol, numPeriodosTimeFrameh, timeFrameh, numPeriodosMMh)

            # Obtiene los balances de la posición y la cuenta del símbolo
            base_free, base_locked, base_total, quote_free, quote_locked, quote_total = obtener_balances(client, symbol, baseAsset, quoteAsset)

            # Determina la señal de compra si se cumplen las condiciones
            if closeActualw < (ultimo_lowW + puntosMargenLowW) < precioMMw and closeActualh < (ultimo_lowh + puntosMargenLowh) < precioMMh:
                # Ejecuta la compra a mercado si se cumplen las condiciones
                if quote_free > balanceQuoteAssetLibreMinOperar and closeActualh < precioUltimaCompraMarket:
                    precioUltimaCompraMarket, volumenUltimaCompraMarket, costoTotalUltimaCompraMarket = compraMarket(symbol, volumenCompra, puntosFactorBeneficioPorcentual)

                    # Calcula el nuevo precio promedio ponderado (DCA) de la posición
                    sumaCostosTotales = DCAcostoTotalPosicion + costoTotalUltimaCompraMarket
                    sumaVolumenesTotales = DCAVolumenPosicion + volumenUltimaCompraMarket
                    nuevoPrecioDCAPosicion = sumaCostosTotales / sumaVolumenesTotales

                    # Calcula el precio de venta con beneficio
                    precioDCAConBeneficio = nuevoPrecioDCAPosicion * (Decimal(1) + Decimal(puntosFactorBeneficioPorcentual))

                    # Actualiza la orden de venta limit con el nuevo precio y volumen
                    actualizarOrdenSellLimit(symbol, precioDCAConBeneficio, sumaVolumenesTotales)
                else:
                    print(f"Balance de {quoteAsset} Insuficiente, APORTA MAS {quoteAsset} AL BALANCE o libera balance Bloqueado")
            else:
                print(f"Precio fuera de Rango de Compra, ESPERANDO ACCION DEL PRECIO")

            # Registra los datos en el archivo CSV
            with open(csv_filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'), closeActualw, closeActualh, precioMMw, precioMMh,
                    ultimo_lowW, ultimo_lowh, base_free, base_locked, base_total, quote_free, quote_locked, quote_total, precioUltimaCompraMarket, nuevoPrecioDCAPosicion, precioDCAConBeneficio
                ])

        except Exception as e:
            print(f"Error durante la ejecución: {e}")
            traceback.print_exc()

        # Espera antes de la siguiente ejecución
        time.sleep(tiempoEntreEjecucion)