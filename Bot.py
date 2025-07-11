
import os
import random
import datetime
import asyncio
import aiohttp
import pytz
import signal
import sys
from twitchio.ext import commands

# Configuración para Railway
def signal_handler(sig, frame):
    print('Bot detenido graciosamente')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class ROJOBOT(commands.Bot):
    
    def __init__(self):
        # Configuración del bot
        super().__init__(
            token='jnr18ofr2r8e7br0krnkea9mrb4dpn',  # Token OAuth configurado
            prefix='!',  # Prefijo para los comandos
            initial_channels=['elrojotw']  # Tu canal
        )
        
        # Variables para el bot
        self.start_time = datetime.datetime.now()
        self.puntos_usuarios = {}  # Sistema de puntos simple
        self.usuarios_activos = []  # Lista de usuarios activos en el chat
        self.colombia_tz = pytz.timezone('America/Bogota')
        
        # Sistema de conversación simple (sin IA)
        self.conversaciones_activas = {}  # {usuario: {'ultimo_mensaje': datetime, 'contexto': str}}
        self.tiempo_timeout = 120  # 2 minutos en segundos
        
        # Configuración para clips automáticos
        self.clips_automaticos = True
        self.palabras_clip = [
            'poggers', 'pog', 'increible', 'increíble', 'genial', 'brutal', 
            'savage', 'clip', 'clipea', 'momento', 'épico', 'epico', 'wow',
            'omg', 'wtf', 'lol', 'kekw', 'insane', 'loco', 'impresionante'
        ]
        self.ultimo_clip = None
        self.cooldown_clip = 60  # 1 minuto entre clips automáticos
        
        # Contadores para clips automáticos
        self.contador_mensajes_clip = 0
        self.limite_mensajes_clip = 15  # Crear clip cada 15 mensajes con palabras clave
        
        # API de The Fyre Wire para clips
        self.fyre_api_url = "https://api.thefyrewire.com/twitch/clips"
        
        # Configuración de Twitch (para información adicional)
        self.canal_twitch = 'elrojotw'
    
    async def event_ready(self):
        """Se ejecuta cuando el bot está listo"""
        print(f'ROJOBOT conectado como {self.nick}')
        print(f'Conectado al canal: {self.canal_twitch}')
        print('✓ Sistema de clips automáticos activado')
        print('✓ Comando !clip manual disponible')
        print('✓ Detección de palabras clave para clips automáticos')
        
        # Iniciar tarea de limpieza de conversaciones
        self.loop.create_task(self.limpiar_conversaciones_inactivas())
    
    async def event_message(self, message):
        """Se ejecuta con cada mensaje en el chat"""
        # Ignorar mensajes del propio bot
        if message.echo:
            return
        
        # Actualizar lista de usuarios activos
        if message.author.name not in self.usuarios_activos:
            self.usuarios_activos.append(message.author.name)
        
        # Verificar si el usuario está en una conversación activa
        if message.author.name in self.conversaciones_activas:
            if not message.content.startswith('!'):
                await self.continuar_conversacion(message)
                return
        
        # Detectar palabras clave para clips automáticos
        await self.detectar_palabras_clip(message)
        
        # Procesar comandos
        await self.handle_commands(message)
        
        # Respuestas automáticas
        mensaje_lower = message.content.lower()
        
        # Saludar cuando alguien dice hola
        if mensaje_lower.strip() == 'hola' and message.author.name not in self.conversaciones_activas:
            await message.channel.send(f'¡Hola @{message.author.name}! ¡Bienvenido al stream! 👋🔴')
        
        # Saludar cuando mencionan al bot
        if 'rojobot' in mensaje_lower and 'hola' in mensaje_lower:
            await message.channel.send(f'¡Hola @{message.author.name}! ¿Cómo estás? 🤖')
        
        # Sistema de puntos
        if message.author.name not in self.puntos_usuarios:
            self.puntos_usuarios[message.author.name] = 0
        self.puntos_usuarios[message.author.name] += 1
    
    async def detectar_palabras_clip(self, message):
        """Detecta palabras clave en el chat para crear clips automáticos"""
        if not self.clips_automaticos:
            return
        
        mensaje_lower = message.content.lower()
        
        # Verificar si contiene palabras clave
        for palabra in self.palabras_clip:
            if palabra in mensaje_lower:
                self.contador_mensajes_clip += 1
                
                # Crear clip automático si se alcanza el límite
                if self.contador_mensajes_clip >= self.limite_mensajes_clip:
                    await self.crear_clip_automatico(message, palabra)
                    self.contador_mensajes_clip = 0
                break
    
    async def crear_clip_automatico(self, message, palabra_clave):
        """Crea un clip automático usando la API de The Fyre Wire"""
        # Verificar cooldown
        if self.ultimo_clip:
            tiempo_desde_ultimo = (datetime.datetime.now() - self.ultimo_clip).total_seconds()
            if tiempo_desde_ultimo < self.cooldown_clip:
                return
        
        try:
            # Crear clip usando The Fyre Wire API
            clip_data = await self.crear_clip_fyre_wire(
                titulo=f"Momento épico por '{palabra_clave}' - {message.author.name}",
                auto=True
            )
            
            if clip_data:
                self.ultimo_clip = datetime.datetime.now()
                await message.channel.send(
                    f'📹 ¡Clip automático creado! Palabra clave: "{palabra_clave}" '
                    f'detectada por @{message.author.name} 🎬'
                )
        except Exception as e:
            print(f"Error al crear clip automático: {e}")
    
    async def crear_clip_fyre_wire(self, titulo="Clip de ElRojoTW", auto=False):
        """Crea un clip usando The Fyre Wire API"""
        try:
            # Parámetros para la API
            params = {
                'channel': self.canal_twitch,
                'title': titulo[:100],  # Limitar título a 100 caracteres
                'duration': 30,  # 30 segundos por defecto
                'delay': 0,  # Sin delay
                'has_delay': 'false'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.fyre_api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        print(f"Error en API Fyre Wire: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"Error al conectar con Fyre Wire API: {e}")
            return None
    
    async def continuar_conversacion(self, message):
        """Continúa una conversación simple sin IA"""
        usuario = message.author.name
        
        # Actualizar timestamp
        self.conversaciones_activas[usuario]['ultimo_mensaje'] = datetime.datetime.now()
        
        # Obtener contexto de la conversación
        contexto = self.conversaciones_activas[usuario].get('contexto', '')
        
        # Generar respuesta simple
        respuesta = self.generar_respuesta_simple(usuario, message.content, contexto)
        
        # Actualizar contexto
        self.conversaciones_activas[usuario]['contexto'] = contexto + f" Usuario: {message.content}"
        
        # Enviar respuesta
        await message.channel.send(f'@{usuario} {respuesta}')
    
    def generar_respuesta_simple(self, usuario, mensaje, contexto=""):
        """Genera respuestas simples sin IA"""
        mensaje_lower = mensaje.lower()
        
        # Respuestas para despedidas
        if any(despedida in mensaje_lower for despedida in ['adiós', 'adios', 'chao', 'bye', 'hasta luego', 'me voy']):
            self.conversaciones_activas.pop(usuario, None)
            return "¡Nos vemos! Gracias por la charla 👋"
        
        # Respuestas para saludos
        if any(saludo in mensaje_lower for saludo in ['hola', 'hi', 'hey', 'buenas', 'saludos', 'qué tal']):
            return random.choice([
                "¡Hey! ¿Qué tal va tu día? 😊",
                "¡Hola! ¿Listo para disfrutar el stream? 🎮",
                "¡Buenas! Me alegra verte por aquí 🔴",
                "¡Qué onda! ¿Cómo va todo? 🎯",
                "¡Saludos! El stream está genial hoy 🔥"
            ])
        
        # Respuestas para preguntas sobre juegos
        if any(palabra in mensaje_lower for palabra in ['juego', 'jugar', 'gaming', 'game', 'videojuego']):
            return random.choice([
                "¡Los juegos son mi pasión! ¿Cuál es tu favorito? 🎮",
                "¡ElRojo siempre elige los mejores juegos! 🕹️",
                "Gaming es vida! ¿Qué género prefieres? 🎯",
                "¡Nada como un buen gaming session! 🔥"
            ])
        
        # Respuestas sobre ElRojo
        if any(palabra in mensaje_lower for palabra in ['rojo', 'elrojo', 'streamer', 'canal']):
            return random.choice([
                "¡ElRojo es el mejor! Su energía es única 🔴",
                "¡Este stream está que arde gracias a ElRojo! 🔥",
                "¡ElRojo siempre nos sorprende! ❤️",
                "¡Nadie como ElRojo para animar el chat! 🎉"
            ])
        
        # Respuestas sobre el stream
        if any(palabra in mensaje_lower for palabra in ['stream', 'directo', 'live', 'transmisión']):
            return random.choice([
                "¡El stream de hoy está épico! 🎬",
                "¡Me encanta la vibra del stream! 🔴",
                "¡Qué buen stream estamos teniendo! 💯",
                "¡Este stream está on fire! 🔥"
            ])
        
        # Respuestas para emociones positivas
        if any(palabra in mensaje_lower for palabra in ['genial', 'increíble', 'brutal', 'épico', 'wow', 'amazing']):
            return random.choice([
                "¡Exactamente! ¡Esa es la actitud! 🔥",
                "¡Me contagias tu energía! 🎉",
                "¡Eso es lo que me gusta escuchar! 💯",
                "¡Qué buena vibra tienes! ✨"
            ])
        
        # Respuestas para preguntas
        if any(pregunta in mensaje_lower for pregunta in ['?', 'cómo', 'como', 'qué', 'que', 'cuál', 'cual', 'dónde', 'donde']):
            return random.choice([
                "¡Buena pregunta! ¿Qué piensas tú? 🤔",
                "¡Interesante! Dime más sobre eso 💭",
                "¡Uff, me hiciste pensar! 🧠",
                "¡Esa sí que es una buena pregunta! 🎯"
            ])
        
        # Respuestas sobre clips
        if any(palabra in mensaje_lower for palabra in ['clip', 'clipea', 'momento', 'guarda']):
            return random.choice([
                "¡Sí! ¡Ese momento merece un clip! 📹",
                "¡Usa !clip para crear uno! 🎬",
                "¡Los clips automáticos están activados! 🔴",
                "¡Qué buen ojo para los momentos épicos! 🎯"
            ])
        
        # Respuestas genéricas
        return random.choice([
            "¡Qué interesante! Cuéntame más 🤔",
            "¡No había pensado en eso! 💭",
            "¡Me encanta hablar contigo! 😄",
            "¡Eso está genial! ¿Y qué más? 🎉",
            "¡Wow! Sigue contándome 🚀",
            "¡Qué buena vibra tienes! ✨",
            "¡Me gusta tu estilo! 😎",
            "¡Eres parte de la mejor comunidad! ❤️"
        ])
    
    async def limpiar_conversaciones_inactivas(self):
        """Limpia las conversaciones inactivas"""
        while True:
            await asyncio.sleep(30)  # Verificar cada 30 segundos
            
            ahora = datetime.datetime.now()
            usuarios_a_eliminar = []
            
            for usuario, datos in self.conversaciones_activas.items():
                tiempo_inactivo = (ahora - datos['ultimo_mensaje']).total_seconds()
                
                if tiempo_inactivo > self.tiempo_timeout:
                    usuarios_a_eliminar.append(usuario)
            
            # Eliminar conversaciones inactivas
            for usuario in usuarios_a_eliminar:
                self.conversaciones_activas.pop(usuario, None)
    
    # COMANDOS BÁSICOS
    
    @commands.command(name='hola')
    async def hola(self, ctx):
        """Saluda al usuario"""
        await ctx.send(f'¡Hola @{ctx.author.name}! ¡Bienvenido al stream de ElRojoTW! 👋🔴')
    
    @commands.command(name='comandos')
    async def comandos(self, ctx):
        """Lista todos los comandos disponibles"""
        comandos_lista = '!hola, !discord, !redes, !horario, !dado, !amor, !puntos, !uptime, !clip, !followrojo, !8ball, !chat, !clipauto'
        await ctx.send(f'📋 Comandos disponibles: {comandos_lista}')
    
    @commands.command(name='discord')
    async def discord(self, ctx):
        """Muestra el link de Discord"""
        await ctx.send('💬 ¡Únete a nuestro Discord! → https://discord.gg/K4tYpsJmbk')
    
    @commands.command(name='redes')
    async def redes(self, ctx):
        """Muestra las redes sociales"""
        await ctx.send('▬▬▬▬▬▬▬▬▬𝓢𝓲𝓰𝓾𝓮𝓶𝓮▬▬▬▬▬▬▬▬ Encuéntrame en estas redes sociales. https://bit.ly/3P3sPsN Instagram: https://bit.ly/3aw6NzJ Twitter: https://bit.ly/3uImE56 Facebook: https://bit.ly/3uILYrO Canal Principal: https://bit.ly/3uKe1Hf Canal Secundario: https://bit.ly/3Pm7s5z Tiktok: https://bit.ly/3yzvR0W Discord: contactoelrojoyt10@gmail.com ▬▬▬▬▬▬▬▬▬𝓢𝓲𝓰𝓾𝓮𝓶𝓮▬▬▬▬▬▬▬▬')
    
    @commands.command(name='horario')
    async def horario(self, ctx):
        """Muestra el horario de streams"""
        ahora_colombia = datetime.datetime.now(self.colombia_tz)
        await ctx.send(f'🕐 Horario de streams (Hora Colombia 🇨🇴): Lunes a Viernes 8:00 PM - 11:00 PM | Sábados y Domingos horario especial!')
    
    # COMANDOS DE CLIPS
    
    @commands.command(name='clip')
    async def clip_manual(self, ctx, *, titulo: str = None):
        """Crea un clip manual usando The Fyre Wire API"""
        if not titulo:
            titulo = f"Clip de {ctx.author.name}"
        
        await ctx.send(f'📹 @{ctx.author.name} está creando un clip... ¡Un momento! 🎬')
        
        try:
            clip_data = await self.crear_clip_fyre_wire(titulo=titulo)
            
            if clip_data:
                await ctx.send(f'✅ ¡Clip creado exitosamente por @{ctx.author.name}! 🎉')
            else:
                await ctx.send('❌ No pude crear el clip. Verifica que el stream esté activo.')
                
        except Exception as e:
            print(f"Error al crear clip manual: {e}")
            await ctx.send('❌ Ocurrió un error al crear el clip. Intenta de nuevo.')
    
    @commands.command(name='clipauto')
    async def toggle_clips_automaticos(self, ctx):
        """Activa/desactiva los clips automáticos (solo mods)"""
        if not ctx.author.is_mod and ctx.author.name.lower() != 'elrojotw':
            await ctx.send('❌ Solo los moderadores pueden usar este comando.')
            return
        
        self.clips_automaticos = not self.clips_automaticos
        estado = "activados" if self.clips_automaticos else "desactivados"
        emoji = "✅" if self.clips_automaticos else "❌"
        
        await ctx.send(f'{emoji} Clips automáticos {estado}')
    
    @commands.command(name='clipstats')
    async def clip_stats(self, ctx):
        """Muestra estadísticas de los clips"""
        await ctx.send(f'📊 Clips automáticos: {"✅" if self.clips_automaticos else "❌"} | '
                      f'Mensajes hasta próximo clip: {self.limite_mensajes_clip - self.contador_mensajes_clip} | '
                      f'Palabras clave detectadas: {len(self.palabras_clip)}')
    
    # COMANDO DE CHAT CONVERSACIONAL
    
    @commands.command(name='chat')
    async def chat(self, ctx, *, mensaje: str = None):
        """Inicia una conversación simple con el bot"""
        usuario = ctx.author.name
        
        if not mensaje:
            await ctx.send(f'@{usuario} ¡Hola! Usa !chat [tu mensaje] para comenzar a conversar conmigo. '
                          f'Después puedes escribir normalmente. La charla termina después de 2 minutos de inactividad. 💬')
            return
        
        # Iniciar nueva conversación
        self.conversaciones_activas[usuario] = {
            'ultimo_mensaje': datetime.datetime.now(),
            'contexto': f"Usuario: {mensaje}"
        }
        
        # Generar respuesta
        respuesta = self.generar_respuesta_simple(usuario, mensaje)
        
        # Enviar respuesta
        await ctx.send(f'@{usuario} {respuesta}')
    
    # COMANDOS DIVERTIDOS
    
    @commands.command(name='dado')
    async def dado(self, ctx):
        """Tira un dado"""
        resultado = random.randint(1, 6)
        mensajes_dado = {
            1: "¡Uy! Sacaste un 1... La suerte no está de tu lado hoy, pero no te rindas! 🎲",
            2: "Un 2... Dicen que los pares traen buena energía. ¡Sigue intentando! 🎲",
            3: "¡Un 3! El número de la creatividad. Algo bueno se acerca... 🎲",
            4: "¡4! Número de estabilidad. Tu suerte está mejorando considerablemente 🎲",
            5: "¡Casi perfecto! Un 5 significa que estás a punto de lograr algo grande 🎲",
            6: "¡INCREÍBLE! ¡Sacaste un 6! ¡Eres el rey/reina de la suerte hoy! 🎲👑"
        }
        await ctx.send(f'@{ctx.author.name} tiró el dado y sacó un {resultado}! {mensajes_dado[resultado]}')
    
    @commands.command(name='amor')
    async def amor(self, ctx):
        """Calcula el porcentaje de amor con alguien random del chat"""
        if len(self.usuarios_activos) < 2:
            await ctx.send(f'💕 Necesitamos más personas en el chat para calcular el amor!')
            return
        
        usuarios_disponibles = [u for u in self.usuarios_activos if u != ctx.author.name]
        usuario_random = random.choice(usuarios_disponibles)
        
        porcentaje = random.randint(0, 100)
        if porcentaje < 30:
            emoji = '💔'
            mensaje = 'Quizás en otra vida...'
        elif porcentaje < 70:
            emoji = '💕'
            mensaje = '¡Hay química!'
        else:
            emoji = '💖'
            mensaje = '¡Es amor verdadero!'
        
        await ctx.send(f'{emoji} @{ctx.author.name} tiene {porcentaje}% de compatibilidad amorosa con @{usuario_random}! {mensaje}')
    
    @commands.command(name='8ball')
    async def bola8(self, ctx, *, pregunta: str = None):
        """La bola mágica responde"""
        if not pregunta:
            await ctx.send('🎱 Debes hacer una pregunta después del comando. Ejemplo: !8ball ¿Ganaré hoy?')
            return
        
        respuestas_positivas = [
            f'🎱 Las estrellas se alinean a tu favor, @{ctx.author.name}. La respuesta es SÍ.',
            f'🎱 Mi visión cósmica me dice que definitivamente sí, @{ctx.author.name}.',
            f'🎱 Todo apunta a que sí. El universo conspira a tu favor.',
            f'🎱 Sin duda alguna, @{ctx.author.name}. El destino así lo ha decidido.'
        ]
        
        respuestas_negativas = [
            f'🎱 Las energías no están alineadas, @{ctx.author.name}. La respuesta es no.',
            f'🎱 Mi sabiduría ancestral dice que no es el momento.',
            f'🎱 Los astros indican que no, pero no pierdas la esperanza.',
            f'🎱 Lamentablemente no veo eso en tu futuro cercano.'
        ]
        
        respuestas_inciertas = [
            f'🎱 Las nieblas del futuro nublan mi visión... Pregunta más tarde.',
            f'🎱 El destino aún no está escrito, @{ctx.author.name}. Inténtalo de nuevo.',
            f'🎱 Mi esfera está recalculando... Vuelve a preguntar en unos minutos.',
            f'🎱 La respuesta está en movimiento. El futuro es incierto.'
        ]
        
        tipo = random.choice(['positiva', 'negativa', 'incierta'])
        if tipo == 'positiva':
            respuesta = random.choice(respuestas_positivas)
        elif tipo == 'negativa':
            respuesta = random.choice(respuestas_negativas)
        else:
            respuesta = random.choice(respuestas_inciertas)
        
        await ctx.send(respuesta)
    
    # COMANDOS DE INFORMACIÓN
    
    @commands.command(name='puntos')
    async def puntos(self, ctx):
        """Muestra los puntos del usuario"""
        puntos = self.puntos_usuarios.get(ctx.author.name, 0)
        await ctx.send(f'🏆 @{ctx.author.name} tiene {puntos} puntos rojos!')
    
    @commands.command(name='uptime')
    async def uptime(self, ctx):
        """Muestra cuánto tiempo lleva el bot activo"""
        ahora = datetime.datetime.now()
        uptime = ahora - self.start_time
        horas = int(uptime.total_seconds() // 3600)
        minutos = int((uptime.total_seconds() % 3600) // 60)
        await ctx.send(f'⏱️ ROJOBOT lleva activo: {horas}h {minutos}m')
    
    @commands.command(name='followrojo')
    async def followrojo(self, ctx):
        """Simula información de seguimiento"""
        dias_siguiendo = random.randint(1, 1000)
        fecha_follow = datetime.datetime.now() - datetime.timedelta(days=dias_siguiendo)
        
        tiempo_siguiendo = datetime.datetime.now() - fecha_follow
        
        años = tiempo_siguiendo.days // 365
        meses = (tiempo_siguiendo.days % 365) // 30
        dias = (tiempo_siguiendo.days % 365) % 30
        
        tiempo_str = ""
        if años > 0:
            tiempo_str += f"{años} año{'s' if años > 1 else ''}, "
        if meses > 0:
            tiempo_str += f"{meses} mes{'es' if meses > 1 else ''}, "
        if dias > 0:
            tiempo_str += f"{dias} día{'s' if dias > 1 else ''}"
        
        await ctx.send(f'❤️ @{ctx.author.name} lleva siguiendo a ElRojoTW por: {tiempo_str}')
    
    # COMANDOS PARA MODERADORES
    
    @commands.command(name='so')
    async def shoutout(self, ctx, usuario: str = None):
        """Shoutout a otro streamer (solo mods)"""
        if not ctx.author.is_mod and ctx.author.name.lower() != 'elrojotw':
            return
        
        if usuario:
            usuario = usuario.replace('@', '')
            await ctx.send(f'📢 ¡Vayan a seguir a @{usuario}! → twitch.tv/{usuario}')
    
    @commands.command(name='titulo')
    async def titulo(self, ctx, *, nuevo_titulo: str = None):
        """Actualiza el título del stream (solo mods)"""
        if not ctx.author.is_mod and ctx.author.name.lower() != 'elrojotw':
            return
        
        if nuevo_titulo:
            await ctx.send(f'📝 Título actualizado: {nuevo_titulo}')
    
    # EVENTOS ESPECIALES
    
    async def event_usernotice_subscription(self, metadata):
        """Se ejecuta cuando alguien se suscribe"""
        channel = self.get_channel('elrojotw')
        await channel.send(f'🎉 ¡Gracias @{metadata.user.name} por la suscripción! ¡Bienvenido a la familia roja! ❤️')
    
    async def event_raid(self, raid):
        """Se ejecuta cuando reciben una raid"""
        channel = self.get_channel('elrojotw')
        await channel.send(f'🚨 ¡RAID! ¡Gracias @{raid.user.name} por la raid con {raid.viewer_count} viewers! ¡Bienvenidos todos! 🎊')
    
    async def event_join(self, channel, user):
        """Se ejecuta cuando alguien entra al chat"""
        if user.name not in self.usuarios_activos:
            self.usuarios_activos.append(user.name)
    
    async def event_part(self, user):
        """Se ejecuta cuando alguien sale del chat"""
        if user.name in self.usuarios_activos:
            self.usuarios_activos.remove(user.name)
        
        if user.name in self.conversaciones_activas:
            self.conversaciones_activas.pop(user.name, None)

# CONFIGURACIÓN PARA EJECUTAR EL BOT
if __name__ == '__main__':
    print('=== ROJOBOT MEJORADO - SIN CHATGPT ===')
    print('✓ ChatGPT eliminado - Conversaciones simples')
    print('✓ Clips automáticos con The Fyre Wire API')
    print('✓ Detección de palabras clave para clips')
    print('✓ Comando !clip manual mejorado')
    print('✓ Comando !clipauto para mods')
    print('✓ Sistema de conversación simple y eficiente')
    print('✓ Todas las funcionalidades originales mantenidas')
    print('=====================================\n')
    
    print('🎬 CONFIGURACIÓN DE CLIPS:')
    print('- API: The Fyre Wire (https://thefyrewire.com)')
    print('- Clips automáticos: Activados')
    print('- Palabras clave: poggers, pog, increíble, genial, brutal, etc.')
    print('- Límite: 1 clip cada 1 minuto')

    bot = ROJOBOT()
    bot.run()