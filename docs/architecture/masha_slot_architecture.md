# Masha: Arquitectura de Ranuras (Slot Architecture) y Filosofía L0

## 1. El Problema Original: Parálisis de Capital
El diseño inicial de Masha (Masha 2.0) obligaba a instanciar un bot por cada símbolo (`symbol="BTCUSDT"`). Con seteos estrictos de promedios móviles (ej. temporalidad semanal `1w` y horaria `1h`), Masha operaba como una "francotiradora". 
El efecto colateral negativo de este enfoque es la **parálisis de capital**: el bot podía pasar semanas o meses en estado `WAIT` sin ejecutar ninguna operación si el símbolo preasignado se encontraba en tendencia alcista o lateral fuerte, desperdiciando el costo de oportunidad.

## 2. El Dilema del Desplome (Market Dump)
La primera alternativa explorada fue instruir a Masha para que comprara *todos* los símbolos que cumplieran la condición dentro de una lista de 100 activos. 
Sin embargo, esta opción viola la gestión de riesgo. En un evento de "Cisne Negro" o desplome sistemático, 40 o 50 monedas cumplirían la condición de retroceso simultáneamente. El bot vaciaría todo el presupuesto de la cuenta comprando decenas de activos, convirtiendo el portafolio en una bolsa de "bagholders" de altcoins sin liquidez para ejecutar los niveles DCA.

## 3. La Filosofía L0: Pequeño, Distribuido, Constante
La operativa de Nivel 0 (L0) se basa en la experimentación empírica en la red real, utilizando posiciones pequeñas pero constantes. La meta es mantener el capital rotando y generando micro-beneficios (DCA) a un alto volumen de operaciones. Estar meses en modo `WAIT` rompe la premisa de la filosofía L0.

## 4. La Solución: Masha "Hunter" (Arquitectura de Ranuras)
La evolución lógica alcanzada es la **Arquitectura de Ranuras (Slot Architecture)** o bloqueo de cacería.

### ¿Cómo funciona?
1. **Configuración Multi-Símbolo**: Masha acepta una lista CSV de símbolos (ej. el Top 100 de Binance).
2. **Fase de Escaneo (Hunting)**: Masha patrulla cíclicamente (ej. cada 59s) su lista de 100 símbolos evaluando la caída frente a los promedios `1w` y `1h`.
3. **El Bloqueo (Lock-in)**: El *primer símbolo* que cumpla las condiciones métricas activa el gatillo. Masha ejecuta la compra inicial y **se bloquea** sobre ese único símbolo. 
4. **Fase de Gestión (DCA)**: A partir del bloqueo, Masha se vuelve temporalmente "ciega" a los otros 99 símbolos. Toda su atención y presupuesto asignado se centra exclusivamente en gestionar el DCA de la moneda elegida, hasta que se llena la orden `sell_limit` (Take Profit).
5. **Liberación**: Una vez completada la operación (posición en 0), la "ranura" de Masha se libera, descartando el símbolo y regresando a la Fase de Escaneo.

### Ventajas de Producción
* **Capital Eficiente**: Masha siempre tendrá "algo" que hacer. Entre 100 monedas de alta capitalización, las oportunidades de retroceso (dips) ocurren a diario.
* **Riesgo Estrictamente Controlado**: 1 Bot = 1 Posición Activa Máxima. Si levantas 10 instancias de Masha, el sistema jamás sobrepasará las 10 posiciones simultáneas, sin importar cuán profundo sea un "crash" global del mercado.
* **Descorrelación**: Desplegando instancias con *offsets* temporales primos (ej. 59s, 71s, 89s), se evita que las Mashas coincidan en el mismo análisis al mismo milisegundo, distribuyendo los gatillos de manera orgánica.
