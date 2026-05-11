# Louise Bot Hub - Dashboard

## 🚀 Acceso Rápido

### **Opción 1: Dashboard Web (RECOMENDADO)**
**Archivo:** `louise_dashboard_compact.html`

**Cómo abrir:**
1. Doble-click en el archivo
2. O arrastra al navegador
3. O click derecho → Abrir con → Navegador

**Ubicaciones:**
- Repo principal: `C:\Users\Dell\Desktop\Pecunator-AccuMonetas\louise_dashboard_compact.html`
- Desktop: `C:\Users\Dell\Desktop\louise_dashboard.html`

**Características:**
- ✅ Sin instalaciones requeridas
- ✅ Funciona inmediatamente
- ✅ Tema oscuro por defecto
- ✅ Bots en lista compacta
- ✅ 4 gráficos: PNL, Weight, Requests, Trades
- ✅ Botones operativos (Pausar, Editar, Eliminar)
- ✅ Actualización en vivo cada 5 segundos
- ✅ Responsive (desktop, tablet, móvil)

---

### **Opción 2: Aplicación Flutter**
**Carpeta:** `desktop_shell/`

**Cómo ejecutar:**
```bash
cd desktop_shell
flutter pub get
flutter run -d windows
```

**Requisitos:**
- ✅ Flutter 3.41.8 (ya instalado)
- ✅ Visual Studio Build Tools (ya disponible)

---

## 📊 Datos

### Conexión a Backend (cuando esté operativo)
Los endpoints están listos en:
```
GET /api/louise/bots
GET /api/louise/metrics
GET /api/louise/weight-governor/status
GET /api/louise/weight-governor/history
GET /api/louise/telemetry/requests
GET /api/louise/telemetry/bandwidth
GET /api/louise/health
```

**Actualmente:** Dashboard usa datos simulados realistas

---

## 🎯 Recomendación

**Para desarrollo y evaluación: Usa el HTML**
- No requiere compilación
- Abre inmediatamente
- Todos los gráficos funcionales
- Puede conectarse a API cuando esté lista

**Para producción: Usa Flutter**
- Interfaz nativa Windows
- Mejor integración SO
- Distribuible como .exe

---

## 📁 Archivos

| Archivo | Descripción |
|---------|-------------|
| `louise_dashboard_compact.html` | **PRINCIPAL** - Dashboard compacto, densa, profesional |
| `louise_dashboard_fixed.html` | Versión con todos los botones operativos |
| `louise_dashboard.html` | Versión extendida original |
| `desktop_shell/` | Proyecto Flutter |
| `runtime/api/routers/louise.py` | API endpoints |

---

**Última actualización:** 2026-05-11
**Estado:** ✅ Listo para usar
