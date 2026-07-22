import discord
from discord.ext import commands
from discord import app_commands
import sys
from app.bot.helper.confighelper import MEMBARR_VERSION, switch, Discord_bot_token, jellyfin_roles
import app.bot.helper.confighelper as confighelper
import app.bot.helper.jellyfinhelper as jelly
from app.bot.helper.message import *
from requests import ConnectTimeout, ConnectionError as ReqConnectionError

maxroles = 10

if switch == 0:
    print("Missing Config.")
    sys.exit()


class Bot(commands.Bot):
    def __init__(self) -> None:
        print("Initializing Discord bot")
        intents = discord.Intents.all()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=".", intents=intents)

    async def on_ready(self):
        print("Bot is online.")
        for guild in self.guilds:
            print("Syncing commands to " + guild.name)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def on_guild_join(self, guild):
        print(f"Joined guild {guild.name}")
        print(f"Syncing commands to {guild.name}")
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def setup_hook(self):
        print("Loading media server connectors")
        await self.load_extension(f'app.bot.cogs.app')


bot = Bot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        try:
            await interaction.response.send_message(
                "You don't have permission to use this command. Administrator permissions are required.",
                ephemeral=True
            )
        except discord.NotFound:
            pass
    elif isinstance(error, app_commands.CommandOnCooldown):
        try:
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.0f} seconds.",
                ephemeral=True
            )
        except discord.NotFound:
            pass
    else:
        print(f"Unhandled command error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while running this command. Check the logs.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred while running this command. Check the logs.",
                    ephemeral=True
                )
        except discord.NotFound:
            pass
        except Exception:
            pass


async def reload():
    await bot.reload_extension(f'app.bot.cogs.app')


jellyfin_commands = app_commands.Group(name="jellyfinsettings", description="Membarr Jellyfin commands")


@jellyfin_commands.command(name="addrole", description="Add a role to automatically add users to Jellyfin")
@app_commands.checks.has_permissions(administrator=True)
async def jellyroleadd(interaction: discord.Interaction, role: discord.Role):
    if len(jellyfin_roles) <= maxroles:
        # Do not add roles multiple times.
        if role.name in jellyfin_roles:
            await embederror(interaction.response, f"Jellyfin role \"{role.name}\" already added.")
            return

        jellyfin_roles.append(role.name)
        saveroles = ",".join(jellyfin_roles)
        confighelper.change_config("jellyfin_roles", saveroles)
        await interaction.response.send_message("Updated Jellyfin roles. Bot is restarting. Please wait a few seconds.",
                                                ephemeral=True)
        print("Jellyfin roles updated. Restarting bot.")
        await reload()
        print("Bot has been restarted. Give it a few seconds.")


@jellyfin_commands.command(name="removerole", description="Stop adding users with a role to Jellyfin")
@app_commands.checks.has_permissions(administrator=True)
async def jellyroleremove(interaction: discord.Interaction, role: discord.Role):
    if role.name not in jellyfin_roles:
        await embederror(interaction.response, f"\"{role.name}\" is currently not a Jellyfin role.")
        return
    jellyfin_roles.remove(role.name)
    confighelper.change_config("jellyfin_roles", ",".join(jellyfin_roles))
    await interaction.response.send_message(f"Membarr will stop auto-adding \"{role.name}\" to Jellyfin",
                                            ephemeral=True)


@jellyfin_commands.command(name="listroles",
                           description="List all roles whose members will be automatically added to Jellyfin")
@app_commands.checks.has_permissions(administrator=True)
async def jellyrolels(interaction: discord.Interaction):
    await interaction.response.send_message(
        "The following roles are being automatically added to Jellyfin:\n" +
        ", ".join(jellyfin_roles), ephemeral=True
    )


@jellyfin_commands.command(name="setup", description="Setup Jellyfin integration")
@app_commands.checks.has_permissions(administrator=True)
async def setupjelly(interaction: discord.Interaction, server_url: str, api_key: str, external_url: str = None):
    # Defer immediately — fail gracefully if interaction already expired
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.NotFound:
        print("Setup command: interaction expired before defer. Ignoring.")
        return
    # get rid of trailing slashes
    server_url = server_url.rstrip('/')
    # Add http:// if no protocol is specified
    if not server_url.startswith(('http://', 'https://')):
        server_url = 'http://' + server_url

    try:
        server_status = jelly.get_status(server_url, api_key)
        if server_status == 200:
            pass
        elif server_status == 401:
            await embederror(interaction.followup, "API key provided is invalid.")
            return
        elif server_status == 403:
            await embederror(interaction.followup, "API key provided does not have permissions.")
            return
        elif server_status == 404:
            await embederror(interaction.followup, "Server endpoint not found. Check the server URL.")
            return
        else:
            await embederror(interaction.followup,
                             f"Unexpected response from Jellyfin (status {server_status}). Check Membarr logs.")
            return
    except ConnectTimeout:
        await embederror(interaction.followup,
                         "Connection to server timed out. Check that Jellyfin is online and reachable.")
        return
    except ReqConnectionError:
        await embederror(interaction.followup,
                         "Could not connect to the server. Verify the URL is correct and Jellyfin is running.")
        return
    except Exception as e:
        print("Exception while testing Jellyfin connection")
        print(type(e).__name__)
        print(e)
        await embederror(interaction.followup, "Unknown error while connecting to Jellyfin. Check Membarr logs.")
        return

    confighelper.change_config("jellyfin_server_url", str(server_url))
    confighelper.change_config("jellyfin_api_key", str(api_key))
    if external_url is not None:
        confighelper.change_config("jellyfin_external_url", str(external_url))
    else:
        confighelper.change_config("jellyfin_external_url", "")
    print("Jellyfin server URL and API key updated. Restarting bot.")
    await interaction.followup.send("Jellyfin server URL and API key updated. Restarting bot.", ephemeral=True)
    await reload()
    print("Bot has been restarted. Give it a few seconds.")


@jellyfin_commands.command(name="setuplibs", description="Setup libraries that new users can access")
@app_commands.checks.has_permissions(administrator=True)
async def setupjellylibs(interaction: discord.Interaction, libraries: str):
    if not libraries:
        await embederror(interaction.response, "libraries string is empty.")
        return
    else:
        # Do some fancy python to remove spaces from libraries string, but only where wanted.
        libraries = ",".join(list(map(lambda lib: lib.strip(), libraries.split(","))))
        confighelper.change_config("jellyfin_libs", str(libraries))
        print("Jellyfin libraries updated. Restarting bot. Please wait.")
        await interaction.response.send_message(
            "Jellyfin libraries updated. Please wait a few seconds for bot to restart.", ephemeral=True)
        await reload()
        print("Bot has been restarted. Give it a few seconds.")


# Enable / Disable Jellyfin integration
@jellyfin_commands.command(name="enable", description="Enable auto-adding users to Jellyfin")
@app_commands.checks.has_permissions(administrator=True)
async def enablejellyfin(interaction: discord.Interaction):
    if confighelper.USE_JELLYFIN:
        await interaction.response.send_message("Jellyfin already enabled.", ephemeral=True)
        return
    confighelper.change_config("jellyfin_enabled", True)
    print("Jellyfin enabled, reloading server")
    confighelper.USE_JELLYFIN = True
    await interaction.response.send_message("Jellyfin enabled. Restarting server. Give it a few seconds.",
                                            ephemeral=True)
    await reload()
    print("Bot has restarted. Give it a few seconds.")


@jellyfin_commands.command(name="disable", description="Disable auto-adding users to Jellyfin")
@app_commands.checks.has_permissions(administrator=True)
async def disablejellyfin(interaction: discord.Interaction):
    if not confighelper.USE_JELLYFIN:
        await interaction.response.send_message("Jellyfin already disabled.", ephemeral=True)
        return
    confighelper.change_config("jellyfin_enabled", False)
    print("Jellyfin disabled, reloading server")
    confighelper.USE_JELLYFIN = False
    await interaction.response.send_message("Jellyfin disabled. Restarting server. Give it a few seconds.",
                                            ephemeral=True)
    await reload()
    print("Bot has restarted. Give it a few seconds.")


bot.tree.add_command(jellyfin_commands)

bot.run(Discord_bot_token)
