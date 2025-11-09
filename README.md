#  Hackaton_CoAfina_Solution — Grupo *TerraBytes*

Este repositorio contiene la solución desarrollada por el grupo **TerraBytes** para la **Hackaton CoAfina 2025**, para el reto **Animación guiada para la visualización de datos ambientales asociados a una red ciudadana de monitoreo**.

---

## Descripción general del proyecto

Nuestra solución consiste en una **plataforma web interactiva** que combina visualización de datos ambientales y un asistente virtual (chatbot).  
El objetivo es facilitar la comprensión de la calidad del aire y las condiciones meteorológicas en diferentes zonas, de una forma **intuitiva, accesible y educativa**.

---

## Componentes principales

### 🗺️ Mapa ambiental interactivo
El mapa muestra un promedio global en una línea de tiempo sobre variables como:

- **PM2.5** (material particulado fino)
- **Temperatura**
- **Humedad relativa**
- **Precipitación**

Donde, de manera dinámica, cuenta con un panel de detalle que despliega las variables mencionadas mediante un sistema de **animaciones visuales** que representan el estado ambiental  
(por ejemplo, una carita feliz cuando el aire es limpio o gotas de lluvia animadas cuando hay alta precipitación).  
Además, cada estación cuenta con su propio panel que permite observar las mismas variables con sus **datos individuales y comportamiento temporal**.

El sistema permite:
- Visualizar los cambios de las variables en el tiempo.
- Observar un promedio global o individual por estación.
- Ajustar la escala de tiempo con animaciones fluidas.

> La visualización fue generada a partir de datos abiertos y optimizada para una experiencia web responsiva.

-detalle 
- Si no hay datos de PM2.5, se asume un estado de aire **limpio** (carita feliz).(esto por temas de que la gran mayaria de los datos muestran el mismo comportamiento de valores menores a 12 PM2.5)  
- Cada variable se acompaña de su valor actual y una animación representativa.  
- El usuario puede desplazar el cursor sobre las animaciones para **ver el valor exacto** en el tiempo. 
---

#### 🌫️ Leyenda de la calidad del aire

El sistema utiliza una **escala visual e intuitiva** para representar la calidad del aire según los niveles de concentración de PM2.5 (en µg/m³) donde mediante una serie de rango se explica al usuario el significado de tener numero altos o bajos de material particulado(PM2.5) donde por ejemplo entre 0 y 10 se considera exelente segun la (OMS) y asi se definen distintos rango donde a mayor PM2.5 mayor contaminacion en el aire existe.

---

#### 🌫️ Ventana flotante de detalle

Cada estación cuenta con una **ventana flotante interactiva** que se despliega al seleccionar una estacion.  
En esta ventana se muestran las **variables más relevantes**, ordenadas por prioridad:

1. **Variables principales:** PM2.5, Temperatura, Humedad y Precipitación.  
2. **Variables opcionales:** Velocidad del viento, Dirección del viento, Presión barométrica, PM1 y PM10.  
3. En caso de datos faltantes, el sistema muestra automáticamente las variables siguientes en la cadena de relevancia.  

Adicionalmente: 
- La interfaz adapta el contenido según el tamaño de pantalla y mantiene una transición suave al abrir o cerrar estaciones.

> Esta ventana funciona como un **panel dinámico de información ambiental**, diseñado para ofrecer los datos de manera mas organizada, donde se puede ver una grafica en el tiempo de la temperatura y del PM2.5, ademas contiene un promedio de esa estacion de los datos, de las variables mencionadas,de forma mas detallada para quienes deseen tener mas informacion aparte de las animaciones.



### 🤖 Chatbot "Eco"

El **chatbot integrado Eco** actúa como un asistente educativo que ayuda a los usuarios a entender:
- Qué representa cada variable.
- Cómo se interpreta la calidad del aire.
- Cómo navegar por el mapa interactivo.
- Conceptos basicos sobre temperatura, calidad del aire, humedad y precipitación.

Esta herramienta busca **fomentar la educación ambiental**, guiando al usuario con un lenguaje claro y cercano.

---

## 🌱 Fuente de datos

Los datos utilizados provienen de la **Red Ambiental RACiMo - Orquídeas**, disponible públicamente en la plataforma **Dataverse de RedCLARA**:

🔗 [https://dataverse.redclara.net/dataset.xhtml?persistentId=doi:10.21348/FK2/UFIOVZ](https://dataverse.redclara.net/dataset.xhtml?persistentId=doi:10.21348/FK2/UFIOVZ)

Estos datos incluyen registros de calidad del aire y variables meteorológicas captadas por sensores de la red ambiental.


##  Objetivo del proyecto

Desarrollar una herramienta de visualización de datos meteorológicos y calidad del aire utilizando el registro de datos de la Red Ambiental Ciudadana de Monitoreo (RACiMo).

> “Comprender el aire que respiramos es el primer paso para mejorar nuestra calidad de vida.”

---


> *El grupo TerraBytes desarrolló esta solución como parte de la Hackaton CoAfina 2025, enfocada en innovación ambiental.*

---

## 🌐 Pagina Web

Se adjunta el link a la pagina web donde se encuentra el mapa, el chatbot e información adicional sobre el proyecto: https://sites.google.com/view/visualizacindedatosambientales?usp=sharing 

---

## 🎥 Video de Youtube

Video explicativo del proyecto: https://www.youtube.com/watch?v=N3M52l5a74k

---

##  Licencia

Este proyecto está bajo la licencia **Attribution-ShareAlike 4.0 International**.

Visualización de datos ambientales asociados a la Red Ambiental Ciudadana de Monitoreo (RACiMo). © 2025 by Isamar Chacón. Roger Zambrano. Andres Bueno. Rubi Lucano is licensed under CC BY-SA 4.0

El codigo esta licenciado bajo la licencia MIT
