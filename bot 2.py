import os

import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
GUILD_ID = 123456789012345678  # ID des Servers, auf dem der Command verfügbar sein soll
OWNER_ID = 1536099560651362378
CONFIRMATION = "ALLES LÖSCHEN"

class ServerLoeschenBot(commands.Bot):
    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

intents = discord.Intents.default()
bot = ServerLoeschenBot(command_prefix="!", intents=intents)

@bot.tree.command(
    name="server_loeschen",
    description="Löscht Kanäle und Rollen auf dem konfigurierten Server."
)
@app_commands.describe(
    bestaetigung=f"Zur Bestätigung exakt {CONFIRMATION} eingeben"
)
async def server_loeschen(
    interaction: discord.Interaction,
    bestaetigung: str
):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "Du darfst diesen Befehl nicht ausführen.",
            ephemeral=True
        )
        return

    if interaction.guild_id != GUILD_ID:
        await interaction.response.send_message(
            "Dieser Befehl funktioniert nur auf dem konfigurierten Server.",
            ephemeral=True
        )
        return

    if bestaetigung != CONFIRMATION:
        await interaction.response.send_message(
            f"Nicht ausgeführt. Gib zur Bestätigung exakt `{CONFIRMATION}` ein.",
            ephemeral=True
        )
        return

    if not interaction.guild.me.guild_permissions.administrator:
        await interaction.response.send_message(
            "Der Bot benötigt Administrator-Berechtigungen.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Löschvorgang gestartet. Nicht löschbare oder höher positionierte Rollen können bestehen bleiben.",
        ephemeral=True
    )

    guild = interaction.guild
    deleted_channels = 0
    deleted_roles = 0

    for channel in list(guild.channels):
        try:
            await channel.delete(reason=f"Angefordert von {interaction.user}")
            deleted_channels += 1
        except (discord.Forbidden, discord.HTTPException):
            pass

    bot_top_role = guild.me.top_role

    for role in list(guild.roles):
        if role.is_default() or role.managed:
            continue
        if role >= bot_top_role:
            continue

        try:
            await role.delete(reason=f"Angefordert von {interaction.user}")
            deleted_roles += 1
        except (discord.Forbidden, discord.HTTPException):
            pass

    try:
        await interaction.followup.send(
            f"Fertig: {deleted_channels} Kanäle und {deleted_roles} Rollen gelöscht.",
            ephemeral=True
        )
    except discord.HTTPException:
        pass

if TOKEN == "DEIN_BOT_TOKEN":
    raise RuntimeError(
        "Setze DISCORD_TOKEN als Umgebungsvariable oder trage deinen Bot-Token ein."
    )

bot.run(TOKEN)
