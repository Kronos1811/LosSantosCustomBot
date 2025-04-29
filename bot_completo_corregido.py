
import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = 1362132888090312984
GUILD = discord.Object(id=GUILD_ID)

conn = sqlite3.connect('asistencias.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    timestamp TEXT,
    tipo TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS facturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    monto INTEGER,
    cliente TEXT,
    timestamp TEXT
)''')
conn.commit()
conn.close()

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"✅ Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")
    canal_logs = discord.utils.get(bot.get_all_channels(), name="📋│logs-bot")
    if canal_logs:
        canales_visibles = [canal.name for canal in bot.get_all_channels() if isinstance(canal, discord.TextChannel)]
        lista_canales = "\n".join(canales_visibles)
        await canal_logs.send(f"🔎 **Canales visibles para el bot:**\n{lista_canales}")
    else:
        print("❌ No se encontró el canal de logs para enviar la lista de canales.")

@bot.event
async def on_member_join(member):
    if member.guild.id == GUILD_ID:
        rol_postulante = discord.utils.get(member.guild.roles, name="Postulante")
        if rol_postulante:
            await member.add_roles(rol_postulante)

@bot.tree.command(name="postularse", description="Inicia tu postulación para Los Santos Custom.", guild=GUILD)
async def postularse(interaction: discord.Interaction):
    categoria = discord.utils.get(interaction.guild.categories, name="POSTULACIONES")
    if not categoria:
        await interaction.response.send_message("❌ No se encontró la categoría POSTULACIONES.", ephemeral=True)
        return
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True),
        discord.utils.get(interaction.guild.roles, name="Staff"): discord.PermissionOverwrite(read_messages=True)
    }
    canal = await interaction.guild.create_text_channel(f"postulacion-{interaction.user.name}", overwrites=overwrites, category=categoria)
    plantilla = (
        f"Por favor completa los siguientes datos:\n\n"
        f"- Nombre de Discord:\n"
        f"- Nombre IC:\n"
        f"- Edad OOC:\n"
        f"- Número de teléfono IC:\n"
        f"- Link de Steam:\n"
        f"- Motivo del por qué quieres unirte:\n"
        f"- Experiencia previa (¿dónde?):\n"
        f"- Horas disponibles semanales:\n"
    )
    await canal.send(f"{interaction.user.mention} ¡Gracias por postularte!\n\n{plantilla}")
    await interaction.response.send_message("✅ ¡Tu canal de postulación fue creado!", ephemeral=True)

@bot.tree.command(name="aceptar", description="Acepta a un postulante como Empleado.", guild=GUILD)
@app_commands.describe(usuario="Menciona al usuario a aceptar")
async def aceptar(interaction: discord.Interaction, usuario: discord.Member):
    if not any(role.name in ["Gerente", "Staff"] for role in interaction.user.roles):
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return
    rol_empleado = discord.utils.get(interaction.guild.roles, name="Empleado")
    canal_resultados = discord.utils.get(interaction.guild.text_channels, name="📢-resultados")
    if rol_empleado and canal_resultados:
        await usuario.add_roles(rol_empleado)
        await canal_resultados.send(
            f"✅ ¡Felicidades {usuario.mention}, has sido aceptado como **Empleado**!\n"
            f"📋 Por favor, **lee la normativa** y mantente atento a los avisos."
        )
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ No se encontró el rol Empleado o el canal resultados.", ephemeral=True)

@bot.tree.command(name="rechazar", description="Rechaza la postulación de un usuario.", guild=GUILD)
@app_commands.describe(usuario="Menciona al usuario a rechazar", motivo="Motivo del rechazo")
async def rechazar(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    if not any(role.name in ["Gerente", "Staff"] for role in interaction.user.roles):
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return
    canal_resultados = discord.utils.get(interaction.guild.text_channels, name="📢-resultados")
    if canal_resultados:
        await canal_resultados.send(
            f"❌ {usuario.mention}, tu postulación ha sido rechazada.\n"
            f"📝 **Motivo:** {motivo}\n"
            f"💪 ¡Sigue intentando! Prepárate mejor y vuelve a postular cuando estés listo."
        )
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ No se encontró el canal resultados.", ephemeral=True)

@bot.tree.command(name="asistencia", description="Marca entrada o salida del turno.", guild=GUILD)
@app_commands.describe(accion="Escribe: entrar o salir")
async def asistencia(interaction: discord.Interaction, accion: str):
    canal_registro = next((c for c in interaction.guild.text_channels if "registros-horas-trabajadas" in c.name), None)
    canal_dia_facturado = next((c for c in interaction.guild.text_channels if "dia-facturado" in c.name), None)
    if not canal_registro or not canal_dia_facturado:
        await interaction.response.send_message("❌ No se encontraron los canales de registros.", ephemeral=True)
        return
    conn = sqlite3.connect('asistencias.db')
    c = conn.cursor()
    if accion.lower() == "entrar":
        c.execute("INSERT INTO asistencias (user_id, username, timestamp, tipo) VALUES (?, ?, ?, ?)",
                  (interaction.user.id, interaction.user.name, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "entrar"))
        conn.commit()
        await canal_registro.send(f"🕒 {interaction.user.mention} ha **entrado** al turno.")
        await interaction.response.send_message("✅ Entrada registrada correctamente.", ephemeral=True)
    elif accion.lower() == "salir":
        c.execute("SELECT timestamp FROM asistencias WHERE user_id = ? AND tipo = 'entrar' ORDER BY id DESC LIMIT 1", (interaction.user.id,))
        resultado = c.fetchone()
        if resultado:
            hora_entrada = datetime.strptime(resultado[0], "%Y-%m-%d %H:%M:%S")
            hora_salida = datetime.utcnow()
            tiempo_trabajado = hora_salida - hora_entrada
            horas, resto = divmod(tiempo_trabajado.seconds, 3600)
            minutos = resto // 60
            c.execute("INSERT INTO asistencias (user_id, username, timestamp, tipo) VALUES (?, ?, ?, ?)",
                      (interaction.user.id, interaction.user.name, hora_salida.strftime("%Y-%m-%d %H:%M:%S"), "salir"))
            conn.commit()
            c.execute("SELECT SUM(monto) FROM facturas WHERE user_id = ? AND timestamp BETWEEN ? AND ?",
                      (interaction.user.id, resultado[0], hora_salida.strftime("%Y-%m-%d %H:%M:%S")))
            total_facturado = c.fetchone()[0] or 0
            await canal_registro.send(
                f"🕒 {interaction.user.mention} ha **salido** del turno.\n"
                f"⏳ Tiempo trabajado: {horas} horas y {minutos} minutos."
            )
            await canal_dia_facturado.send(
                f"💰 {interaction.user.mention} facturó un total de **{total_facturado}$** en su turno."
            )
            await interaction.response.send_message("✅ Salida registrada correctamente.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No se encontró una entrada previa.", ephemeral=True)
    conn.close()

@bot.tree.command(name="factura", description="Registra una factura (captura opcional).", guild=GUILD)
@app_commands.describe(cliente="Nombre del cliente", monto="Monto facturado")
async def factura(interaction: discord.Interaction, cliente: str, monto: int):
    canal_registro = next((c for c in interaction.guild.text_channels if "registros-facturacion" in c.name), None)
    if canal_registro is None:
        await interaction.response.send_message("❌ No se encontró el canal de registros.", ephemeral=True)
        return
    if monto <= 0:
        await interaction.response.send_message("❌ El monto debe ser mayor a 0.", ephemeral=True)
        return
    conn = sqlite3.connect('asistencias.db')
    c = conn.cursor()
    c.execute("INSERT INTO facturas (user_id, username, monto, cliente, timestamp) VALUES (?, ?, ?, ?, ?)",
              (interaction.user.id, interaction.user.name, monto, cliente, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    mensaje = f"💵 {interaction.user.mention} registró una factura de **{monto}$** para **{cliente}**."
    await canal_registro.send(mensaje)
    await interaction.response.send_message("✅ Factura registrada correctamente.", ephemeral=True)

bot.run(TOKEN)
