# Prompt para Opus — Rediseño visual completo del Mesh Event Scheduler

## Contexto

El frontend actual (`apps/frontend`) se construyó a base de parches puntuales,
mediaqueries y ajustes componente por componente. Funciona, pero no tiene
identidad visual propia: parece una plantilla genérica, no un producto
terminado. Ese enfoque incremental nunca iba a producir una pasada de diseño
coherente — hace falta tratarlo como un rediseño de conjunto, no más ajustes
sueltos.

## Prompt

```
Actuá como el lead de diseño de un estudio que le da a cada cliente una
identidad visual distinta e irrepetible. Este cliente ya rechazó una primera
versión por sentirse genérica, de plantilla, "trabajo de curso" — no parece
una aplicación real. Te está pagando por un punto de vista deliberado y
propio, no por ajustes de CSS sueltos.

Invocá el skill frontend-design y usalo con una pasada de diseño de conjunto
completa (spec kit), no como una serie de parches:

1. Brainstorming primero. Antes de tocar código, generá un spec kit del
   diseño:
   - Paleta: 4-6 colores base con hex, nombrados por su rol.
   - Tipografía: familias elegidas y su rol (display/body), con escala
     tipográfica intencional.
   - Layout: concepto de layout en prosa + wireframes ASCII, con guía de
     alineación.
   - Principios: qué hace que este diseño sea específico para ESTE producto
     (un programador de horarios para actuadores físicos sobre una red mesh
     LoRa — no un SaaS genérico, no un dashboard financiero).

2. Autocrítica contra el brief. Revisá el spec kit: ¿alguna parte de esto es
   el default genérico que producirías para cualquier app similar (fondo
   crema + serif display + acento terracota; card kit con border-radius
   uniforme y sombra gris; eyebrows en mayúsculas; iconos de flecha
   genéricos)? Si es así, descartala y reemplazala por algo elegido para
   este producto específico.

3. Implementación. Recién ahí, aplicá el spec kit a toda la aplicación
   (`apps/frontend`) — desktop y mobile — como una pasada de conjunto:
   paleta, tipografía, jerarquía visual, iconografía, estados vacíos,
   modales, calendario semanal/mensual, drawer de eventos. No como
   mediaqueries agregadas sobre el diseño viejo.

4. Restricciones técnicas del proyecto (no negociables):
   - TS vanilla sin framework, Vite. Cero dependencias de runtime nuevas
     (sin CDN de iconos/fuentes externas salvo que ya estén en el proyecto).
   - Debe seguir funcionando igual en desktop y mobile (breakpoint 640px ya
     usado en el proyecto), con soporte real de teclado/foco visible.
   - Regla de oro del proyecto: si la solución complica el código o la
     depuración futura, buscá el camino menos complicado antes de aceptarla.
   - Comentarios en código solo si aportan un "por qué" no obvio — nunca
     para explicar qué hace la línea de al lado.
   - Testing en mobile: usar emulación real de dispositivo en DevTools,
     nunca resize de ventana de escritorio.

Entregá primero el spec kit (paso 1 + 2) para validación antes de tocar
código de producción.
```
