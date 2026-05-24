# OpenClaw Mission Control Dashboard

Un dashboard web simple para monitorear el estado de tus agentes y subagentes de OpenClaw en tiempo real.

## Características

- ✅ Visualización en tiempo real de sesiones y subagentes
- ✅ Estado de agentes (running, done, error)
- ✅ Métricas de duración, tokens y costos
- ✅ Historial de tareas completadas
- ✅ Auto-actualización cada 30 segundos
- ✅ Diseño responsivo para móvil y escritorio
- ✅ Tema profesional con gradientes y sombras

## Estructura

```
mission-control/
├── index.html          # Dashboard principal
└── README.md           # Este archivo
```

## Uso

1. Abre el archivo `index.html` en tu navegador web preferido:
   ```bash
   # Desde la carpeta mission-control
   open index.html     # macOS
   xdg-open index.html # Linux
   start index.html    # Windows
   ```

2. El dashboard se actualizará automáticamente cada 30 segundos
3. También puedes hacer clic en el botón "🔄 Actualizar" para forzar una actualización

## Navegación

El dashboard tiene cuatro pestañas:

### 📊 Resumen
- Estadísticas generales: sesiones totales, activas, tareas en ejecución
- Lista de tareas recientes

### 👥 Agentes
- Lista detallada de todas las sesiones y subagentes
- Información de cada agente: estado, modelo, duración, tokens, etc.

### ⚙️ Tareas
- Vista enfocada en las tareas de subagentes
- Detalles de cada tarea en ejecución o completada

### 📜 Historial
- Historial cronológico de tareas completadas
- Ordenado por fecha de finalización (más reciente primero)

## Personalización

Este dashboard está diseñado como punto de partida. Para personalizarlo:

1. **Modificar la fuente de datos**: Actualmente usa datos de ejemplo. Para conectarlo realmente a OpenClaw, reemplazar la función `loadData()` con llamadas reales a las APIs de sesiones y subagentes.

2. **Añadir más métricas**: Podrías incluir:
   - Uso de CPU/memoria
   - Costos estimados por modelo
   - Tasa de éxito/error
   - Tendencias de rendimiento

3. **Mejorar la UI**: 
   - Añadir gráficos de tendencias
   - Notificaciones en tiempo real
   - Filtros y búsqueda
   - Exportar datos a CSV/JSON

## Próximos pasos sugeridos

1. Conectar a las APIs reales de OpenClaw:
   - `sessions_list` para obtener todas las sesiones
   - `sessions_history` para obtener detalles de sesiones específicas
   - `subagents` para monitorear subagentes activos

2. Añadir webhooks o polling inteligente para actualizaciones en tiempo real sin delay fijo

3. Implementar almacenamiento local para mantener historial incluso cuando el dashboard se cierra

4. Añadir alertas visuales para tareas fallidas o que excedan ciertos umbrales de tiempo

## Tecnologías usadas

- HTML5 semántico
- CSS3 moderno (variables, flexbox, grid, animaciones)
- JavaScript vanilla (sin frameworks)
- Diseño responsivo
- Accesibilidad básica

## Licencia

MIT - Siéntete libre de usar, modificar y distribuir este dashboard para tus necesidades de monitoreo de agentes OpenClaw.