# Thusnelda: Sub-Account Isolation Architectural Doctrine

## 1. El Problema de la Contaminación del Equity
Thusnelda es un bot diseñado para operar con una estrategia de **canasta multi-símbolo (basket)**. 
A diferencia de Masha o Dorothy (que manejan el tracking de profit token por token), Thusnelda evalúa el **Equity Total** de la cuenta para decidir su evento de cosecha (`harvest`).

El código calcula el objetivo de venta de esta manera:
```python
# Si la canasta representa el 100% de la cuenta, un profit_target del 6% 
# se alcanza cuando la canasta sube un 6%.
harvest_target = self._peak_equity_usdt * (1 + profit_target_pct)
```

Si Thusnelda se ejecuta en la misma cuenta principal donde hay otros fondos (Earn, Staking, Hold, o los tokens de otros bots), el `_peak_equity_usdt` será masivo. Por ende, para lograr que la cuenta suba un 6% total, la pequeña canasta de tokens tendría que revalorizarse a niveles absurdos (e.g. 500%), haciendo el "Harvest" inalcanzable.

## 2. El Problema de la Autodestrucción Mutua
Si se despliegan **2 o más bots Thusnelda en la misma cuenta**, se aniquilarán mutuamente en el momento del harvest.
El código de liquidación ordena la venta a mercado del balance total libre de cualquier activo que no sea USDT:
```python
for b in balances:
    # VENDE TODO LO QUE HAYA EN LA CUENTA
    client.order_market_sell(...)
```
Si `Thus-1` decide cosechar, venderá los tokens que `Thus-2` estaba holdeando para su propia estrategia, quebrando el DCA y registrando pérdidas prematuras.

## 3. Regla de Oro en Producción
**UNA SUBCUENTA = UN BOT THUSNELDA**

1. **Aislamiento Estricto**: Cada instancia de Thusnelda debe correr usando una API Key que apunte a una Subcuenta dedicada de Binance de forma exclusiva.
2. **Canastas Múltiples**: Si solo posees una subcuenta, no levantes varias instancias de Thusnelda. Puedes unificar todos los tokens en un solo bot Thusnelda:
   `symbols_csv: "PEPEUSDT,SUIUSDT,INJUSDT,FETUSDT"`
3. **El Profit se mantiene normal**: Al tener la canasta en aislamiento, el profit estándar del 6% (0.06) funcionará de manera esperada, ya que cualquier movimiento del equity estará atado exclusivamente al valor de mercado de la canasta operada.
