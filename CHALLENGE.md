# Challenge — Reporting & Automation

## El contexto

Trabajás en el equipo que le arma reportes a las distintas áreas de negocio de un
marketplace online. Una de esas áreas es la de artículos deportivos.

Entre el **14 y el 30 de julio de 2026** se jugaron los Juegos Olímpicos, y durante esas
semanas se vendió mucha mercadería relacionada: camisetas, álbumes de figuritas,
merchandising oficial y no oficial.

## El pedido

Te llega este mail del equipo comercial de artículos deportivos:

> **Asunto: Venta de Olimpiadas para la review del jueves**
>
> Hola! Necesitamos saber cuánto vendimos por las Olimpiadas de este año. Lo pide el
> director para la review del jueves.
>
> Además del número, lo que más nos importa es entender si nos conviene prepararnos
> distinto para el próximo evento grande: cuánto duró el efecto, si valió la pena el
> merchandising oficial, si hubo países donde funcionó mejor. Algo que nos ayude a
> decidir.
>
> Para que puedan identificar los productos: hay una marca licenciataria que vende el
> merchandising oficial, tiene una cuenta por país y todo lo que publica es del evento.
> Los IDs son 700100 (Argentina), 700200 (Brasil), 700300 (México), 700400 (Chile) y
> 700500 (Colombia).
>
> El resto lo venden vendedores particulares, ahí no hay forma directa de saberlo — se
> identifican por el título de la publicación, buscando menciones al evento
> (*olimpiadas*, *juegos olímpicos*, *olímpico*). Fíjense en las categorías de
> camisetas, álbumes y cartas, que es donde se vende este tipo de cosas.
>
> Si pueden abrirlo por país mejor, y nos sirve ver cómo se movió antes, durante y
> después.
>
> Gracias!

Eso es todo lo que tenemos. No hay un pedido más detallado.

## Los datos

En la carpeta `data/` hay tres archivos con las ventas del área entre el **1 de mayo y
el 31 de agosto de 2026**. Están en cinco países y los montos ya vienen convertidos a
dólares.

### `ventas.csv`

Una fila por venta.

| Campo | Qué es |
|---|---|
| `venta_id` | Identificador de la venta |
| `pais` | Argentina, Brasil, México, Chile o Colombia |
| `fecha` | Día en que se concretó la venta |
| `producto_id` | Qué producto se vendió — se cruza con `productos.csv` |
| `unidades` | Cuántas unidades |
| `monto_usd` | Monto total de la venta, en dólares |

### `productos.csv`

El catálogo. Una fila por producto publicado.

| Campo | Qué es |
|---|---|
| `producto_id` | Identificador del producto |
| `pais` | País donde está publicado |
| `titulo` | Título de la publicación. **Lo escribe cada vendedor a mano**, así que no sigue ningún formato |
| `categoria` | En qué categoría del sitio está publicado — se cruza con `categorias.csv` |
| `vendedor_id` | Quién lo vende |

### `categorias.csv`

El listado de categorías del sitio, con su nombre.

| Campo | Qué es |
|---|---|
| `categoria` | Identificador de la categoría |
| `categoria_nombre` | Nombre descriptivo |

Ningún campo indica si un producto es de los Juegos Olímpicos o no: no hay una marca ni
una categoría que los agrupe. Están mezclados con el resto del catálogo.

## Qué esperamos

**1. Un entregable para el equipo comercial.**

Lo van a abrir en una review, con el director presente, que le va a dedicar dos
minutos. Tiene que sostenerse solo.

El formato lo elegís vos: una presentación, un HTML, un dashboard, lo que consideres que
resuelve mejor este pedido.

Incluí los hallazgos que te parezcan relevantes y las conclusiones que sacaste, en el
formato que prefieras.

**2. Las consultas SQL que usaste.**

Completas, en un archivo aparte. No hace falta que estén dentro del entregable.

**3. Unas líneas sobre escala.**

Si el mes que viene otra área pide lo mismo para un evento distinto, ¿qué harías
diferente?

## Un par de cosas

Podés usar las herramientas que uses habitualmente, IA incluida. Si la usaste, contanos
para qué.

Cualquier duda sobre el pedido, escribinos. Si preferís resolverla por tu cuenta,
contanos qué criterio tomaste.
