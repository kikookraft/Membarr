import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import app.bot.helper.db as db
import app.bot.helper.jellyfinhelper as jelly
from app.bot.helper.textformat import bcolors
import texttable
from app.bot.helper.message import *
from app.bot.helper.confighelper import *

CONFIG_PATH = 'app/config/config.ini'
BOT_SECTION = 'bot_envs'

jellyfin_configured = True

config = configparser.ConfigParser()
config.read(CONFIG_PATH, encoding='utf-8')

# Get Jellyfin config
try:
    JELLYFIN_SERVER_URL = config.get(BOT_SECTION, 'jellyfin_server_url')
    JELLYFIN_API_KEY = config.get(BOT_SECTION, "jellyfin_api_key")
except:
    print("Could not load Jellyfin config")
    jellyfin_configured = False

# Get Jellyfin roles config
try:
    jellyfin_roles = config.get(BOT_SECTION, 'jellyfin_roles')
except:
    jellyfin_roles = None
if jellyfin_roles:
    jellyfin_roles = list(jellyfin_roles.split(','))
else:
    jellyfin_roles = []

# Get Jellyfin libs config
try:
    jellyfin_libs = config.get(BOT_SECTION, 'jellyfin_libs')
except:
    jellyfin_libs = None
if jellyfin_libs is None:
    jellyfin_libs = ["all"]
else:
    jellyfin_libs = list(jellyfin_libs.split(','))

# Get Enable config
try:
    USE_JELLYFIN = config.get(BOT_SECTION, 'jellyfin_enabled')
    USE_JELLYFIN = USE_JELLYFIN.lower() == "true"
except:
    USE_JELLYFIN = False

try:
    JELLYFIN_EXTERNAL_URL = config.get(BOT_SECTION, "jellyfin_external_url")
    if not JELLYFIN_EXTERNAL_URL:
        JELLYFIN_EXTERNAL_URL = JELLYFIN_SERVER_URL
except:
    JELLYFIN_EXTERNAL_URL = JELLYFIN_SERVER_URL
    print("Could not get Jellyfin external url. Defaulting to server url.")


class app(commands.Cog):
    # App command groups
    jellyfin_commands = app_commands.Group(name="jellyfin", description="Membarr Jellyfin commands")
    membarr_commands = app_commands.Group(name="membarr", description="Membarr general commands")

    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print('------')
        print("{:^41}".format(f"MEMBARR V {MEMBARR_VERSION}"))
        print(f'Made by Yoruio https://github.com/Yoruio/\n')
        print(f'Forked from Invitarr https://github.com/Sleepingpirates/Invitarr')
        print(f'Named by lordfransie')
        print(f'Logged in as {self.bot.user} (ID: {self.bot.user.id})')
        print('------')

        if jellyfin_roles is None or len(jellyfin_roles) == 0:
            print('Configure Jellyfin roles to enable auto invite to Jellyfin after a role is assigned.')
    
    async def getusername(self, after):
        username = None
        await embedinfo(after, f"Welcome To Jellyfin! Please reply with your username to be added to the Jellyfin server!")
        await embedinfo(after, f"If you do not respond within 24 hours, the request will be cancelled, and the server admin will need to add you manually.")
        while (username is None):
            def check(m):
                return m.author == after and not m.guild
            try:
                username = await self.bot.wait_for('message', timeout=86400, check=check)
                if(jelly.verify_username(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, str(username.content))):
                    return str(username.content)
                else:
                    username = None
                    message = "This username is already chosen. Please select another username."
                    await embederror(after, message)
                    continue
            except asyncio.TimeoutError:
                message = "Timed out. Please contact the server admin directly."
                print("Jellyfin user prompt timed out")
                await embederror(after, message)
                return None
            except Exception as e:
                await embederror(after, "Something went wrong. Please try again with another username.")
                print (e)
                username = None
    
    async def addtojellyfin(self, username, password, response):
        if not jelly.verify_username(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, username):
            await embederror(response, f'An account with username {username} already exists.')
            return False

        if jelly.add_user(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, username, password, jellyfin_libs):
            return True
        else:
            await embederror(response, 'There was an error adding this user to Jellyfin. Check logs for more info.')
            return False

    async def removefromjellyfin(self, username, response):
        if jelly.verify_username(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, username):
            await embederror(response, f'Could not find account with username {username}.')
            return
        
        if jelly.remove_user(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, username):
            await embedinfo(response, f'Successfully removed user {username} from Jellyfin.')
            return True
        else:
            await embederror(response, f'There was an error removing this user from Jellyfin. Check logs for more info.')
            return False

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if jellyfin_roles is None or len(jellyfin_roles) == 0:
            return
        roles_in_guild = after.guild.roles
        role = None
        jellyfin_processed = False

        # Check Jellyfin roles
        if jellyfin_configured and USE_JELLYFIN:
            for role_for_app in jellyfin_roles:
                for role_in_guild in roles_in_guild:
                    if role_in_guild.name == role_for_app:
                        role = role_in_guild

                    # Jellyfin role was added
                    if role is not None and (role in after.roles and role not in before.roles):
                        print("Jellyfin role added")
                        username = await self.getusername(after)
                        print("Username retrieved from user")
                        if username is not None:
                            await embedinfo(after, "Got it, we will be creating your Jellyfin account shortly!")
                            password = jelly.generate_password(16)
                            if jelly.add_user(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, username, password, jellyfin_libs):
                                db.save_user_jellyfin(str(after.id), username)
                                await asyncio.sleep(2)
                                await self.send_credentials(after, username, password)
                            else:
                                await embederror(after, 'There was an error creating your Jellyfin account. Please contact a server admin.')
                        jellyfin_processed = True
                        break
                        jellyfin_processed = True
                        break

                    # Jellyfin role was removed
                    elif role is not None and (role not in after.roles and role in before.roles):
                        print("Jellyfin role removed")
                        try:
                            user_id = after.id
                            username = db.get_jellyfin_username(user_id)
                            jelly.remove_user(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, username)
                            deleted = db.remove_jellyfin(user_id)
                            if deleted:
                                print("Removed Jellyfin from {}".format(after.name))
                                #await secure.send(plexname + ' ' + after.mention + ' was removed from plex')
                            else:
                                print("Cannot remove Jellyfin from this user")
                            await embedinfo(after, "You have been removed from Jellyfin")
                        except Exception as e:
                            print(e)
                            print("{} Cannot remove this user from Jellyfin.".format(username))
                        jellyfin_processed = True
                        break
                if jellyfin_processed:
                    break

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if USE_JELLYFIN and jellyfin_configured:
            jellyfin_username = db.get_jellyfin_username(member.id)
            if jellyfin_username and jellyfin_username not in ("No users found", "error in fetching from db", "username cannot be empty"):
                jelly.remove_user(JELLYFIN_SERVER_URL, JELLYFIN_API_KEY, jellyfin_username)
            
        deleted = db.delete_user(member.id)
        if deleted:
            print("Removed {} from db because user left discord server.".format(member.name))

    @app_commands.checks.has_permissions(administrator=True)
    @jellyfin_commands.command(name="invite", description="Invite a Discord user to Jellyfin")
    async def jellyfininvite(self, interaction: discord.Interaction, member: discord.Member, username: str):
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            print("Invite command: interaction expired before defer. Ignoring.")
            return
        password = jelly.generate_password(16)
        if await self.addtojellyfin(username, password, interaction.followup):
            await self.send_credentials(member, username, password)
            await embedinfo(interaction.followup, f"Jellyfin account created for {member.mention}")

    @app_commands.checks.has_permissions(administrator=True)
    @jellyfin_commands.command(name="remove", description="Remove a user from Jellyfin")
    async def jellyfinremove(self, interaction: discord.Interaction, username: str):
        await self.removefromjellyfin(username, interaction.response)

    async def send_credentials(self, member: discord.Member, username: str, password: str):
        """Send a nicely formatted credential message to a user via DM."""
        embed = discord.Embed(
            title="🎬 Welcome to Jellyfin!",
            description="Your account has been created. Here are your login details:",
            color=0xAA5CC3
        )
        embed.add_field(name="🌐 Server URL", value=JELLYFIN_EXTERNAL_URL, inline=False)
        embed.add_field(name="👤 Username", value=f"`{username}`", inline=True)
        embed.add_field(name="🔑 Password", value=f"||`{password}`||", inline=True)
        embed.add_field(
            name="📋 Instructions",
            value=f"1. Go to {JELLYFIN_EXTERNAL_URL}\n"
                  "2. Log in with the credentials above\n"
                  "3. Change your password after logging in\n"
                  "4. Enjoy!"
                  "\n\n*Note: You can request films on https://request.kikookraft.fr (same credentials as Jellyfin).*",
            inline=False
        )
        embed.set_footer(text="Enjoy your media! 🍿")
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            print(f"Could not DM {member.name} — they have DMs disabled.")
    
    @app_commands.checks.has_permissions(administrator=True)
    @membarr_commands.command(name="dbadd", description="Add a user to the Membarr database")
    async def dbadd(self, interaction: discord.Interaction, member: discord.Member, jellyfin_username: str = ""):
        jellyfin_username = jellyfin_username.strip()

        try:
            db.save_user_jellyfin(str(member.id), jellyfin_username)
            await embedinfo(interaction.response, 'User was added to the database.')
        except Exception as e:
            await embederror(interaction.response, 'There was an error adding this user to database. Check Membarr logs for more info')
            print(e)

    @app_commands.checks.has_permissions(administrator=True)
    @membarr_commands.command(name="dbls", description="View Membarr database")
    async def dbls(self, interaction: discord.Interaction):

        embed = discord.Embed(title='Membarr Database.')
        all = db.read_all()
        table = texttable.Texttable()
        table.set_cols_dtype(["t", "t", "t"])
        table.set_cols_align(["c", "c", "c"])
        header = ("#", "Name", "Jellyfin")
        table.add_row(header)
        for index, peoples in enumerate(all):
            index = index + 1
            id = int(peoples[1])
            dbuser = self.bot.get_user(id)
            dbjellyfin = peoples[3] if peoples[3] else "No Jellyfin"
            try:
                username = dbuser.name
            except:
                username = "User Not Found."
            embed.add_field(name=f"**{index}. {username}**", value=dbjellyfin+'\n', inline=False)
            table.add_row((index, username, dbjellyfin))
        
        total = str(len(all))
        if(len(all)>25):
            f = open("db.txt", "w")
            f.write(table.draw())
            f.close()
            await interaction.response.send_message("Database too large! Total: {total}".format(total = total),file=discord.File('db.txt'), ephemeral=True)
        else:
            await interaction.response.send_message(embed = embed, ephemeral=True)
        
            
    @app_commands.checks.has_permissions(administrator=True)
    @membarr_commands.command(name="dbrm", description="Remove user from Membarr database")
    async def dbrm(self, interaction: discord.Interaction, position: int):
        embed = discord.Embed(title='Membarr Database.')
        all = db.read_all()
        for index, peoples in enumerate(all):
            index = index + 1
            id = int(peoples[1])
            dbuser = self.bot.get_user(id)
            dbjellyfin = peoples[3] if peoples[3] else "No Jellyfin"
            try:
                username = dbuser.name
            except:
                username = "User Not Found."
            embed.add_field(name=f"**{index}. {username}**", value=dbjellyfin+'\n', inline=False)

        try:
            position = int(position) - 1
            id = all[position][1]
            discord_user = await self.bot.fetch_user(id)
            username = discord_user.name
            deleted = db.delete_user(id)
            if deleted:
                print("Removed {} from db".format(username))
                await embedinfo(interaction.response,"Removed {} from db".format(username))
            else:
                await embederror(interaction.response,"Cannot remove this user from db.")
        except Exception as e:
            print(e)

async def setup(bot):
    await bot.add_cog(app(bot))
