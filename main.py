import discord, config, random, time, traceback, datetime, logging
from datetime import datetime
from typing import List, Optional
from discord.ext import commands
from modules import nitro
from simplejsondb import DatabaseFolder
from messageutils import error_template

bot = commands.Bot(command_prefix=",", intents=discord.Intents.all())
nitro_db = DatabaseFolder('nitro-db', default_factory=lambda _: list())

fansbotlog = logging.getLogger('discord.fansbot')

@bot.event
async def on_ready():
    fansbotlog.info(f"Logged in as {bot.user.name}.")

    if nitro_db["NitroSIDs"] == None:
        nitro_db["NitroSIDs"] = { "region": [ "Northern Ireland", "Scotland", "Wales", "South", "East Midlands", "West Midlands", "East Yorkshire", "North West", "North East", "London", "Sourth East", "South West", "West", "East", "South", "Yorks" ], "channels": [ "BBC News [UK]", "BBC News [World]", "BBC One", "BBC Two", "BBC Three", "BBC Four", "Cbeebies", "CBBC", "BBC Parliament", "BBC Alba", "BBC Scotland" ], "BBC News [World]": "bbc_world_service", "BBC News [UK]": "bbc_news24", "BBC One Scotland": "bbc_one_scotland", "BBC One North East": "bbc_one_north_east", "BBC One North West": "bbc_one_north_west", "BBC One East Midlands": "bbc_one_east_midlands", "BBC One West Midlands": "bbc_one_west_midlands", "BBC One East Yorkshire": "bbc_one_east_yorkshire", "BBC One London": "bbc_one_london", "BBC One South East": "bbc_one_south_east", "BBC One South West": "bbc_one_south_west", "BBC One Northern Ireland": "bbc_one_northern_ireland", "BBC One Wales": "bbc_one_wales", "BBC One West": "bbc_one_west", "BBC One East": "bbc_one_east", "BBC One South": "bbc_one_south", "BBC One Yorks": "bbc_one_yorks", "BBC One": "bbc_one_hd", "BBC Two England": "bbc_two_england", "BBC Two Scotland": "bbc_two_scotland", "BBC Two Northern Ireland": "bbc_two_northern_ireland_digital", "BBC Two Wales": "bbc_two_wales_digital", "BBC Two": "bbc_two_hd", "BBC Three": "bbc_three_hd", "BBC Four": "bbc_four_hd", "CBeebies": "cbeebies_hd", "CBBC": "cbbc_hd", "BBC Parliament": "bbc_parliament", "BBC Alba": "bbc_alba_hd", "BBC Scotland": "bbc_scotland_hd" }
        print("Nitro DB values missing, automatically added.")

    return

# should only be used for debugging
# @bot.event
# async def on_app_command_completion(int: discord.Interaction, cmd: discord.app_commands.Command):
#     fansbotlog.info(f"Command {cmd.name} ran by {int.user.name}")
#     return

@bot.event
async def on_message(message: discord.Message):
    if "bbc fans bot" in message.content.lower() or bot.user.mentioned_in(message):
        await message.channel.send("hellow!")

    await bot.process_commands(message)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.timed_out_until == None and after.timed_out_until != None:
        to_until_a = nitro.dt_to_timestamp(after.timed_out_until, "R")
        to_until_b = nitro.dt_to_timestamp(after.timed_out_until, "f")

        embed = discord.Embed(title="Member timed out", colour=discord.Colour.brand_red())
        embed.add_field(name="Timed out until", value=f"{to_until_a} ({to_until_b})")
        embed.add_field(name="User", value=f"{after.mention}")
        embed.timestamp = datetime.now()

        await bot.get_guild(1016626731785928715).get_channel(1060597991347593297).send(embed=embed)

@bot.command()
async def ping(ctx: commands.Context):
    await ctx.send(content=f"## Pong!\nMy ping is {round(bot.latency * 1000)}ms.")

@bot.command(name="sync")
async def sync(interaction: commands.Context):
    owner = await bot.is_owner(interaction.author)
    if owner:
        m = await interaction.send("Syncing....")
        await bot.tree.sync()
        await m.edit(content="Synced!")
        return
    else:
        m = await interaction.send(content="You don't have the permissions to do this!")
        await interaction.message.delete(10)
        await m.delete(10)
        return

@bot.hybrid_command(name="aaron", description="Sends a random picture of Aaron Heslehurst!")
async def aaron(interaction: commands.Context):
    no = random.randint(0, 4)
    match no:
        case 2: fileformat = "webp"
        case _: fileformat = "jpg"
    image = discord.File(f"images/aaron/{no + 1}.{fileformat}")
    await interaction.send(file=image)

async def programme_sid_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
    options = nitro_db['NitroSIDs']['channels']
    return [
        discord.app_commands.Choice(name=option, value=option)
        for option in options if current.lower() in option.lower()
    ]

async def programme_region_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
    options = nitro_db['NitroSIDs']['region']
    return [
        discord.app_commands.Choice(name=option, value=option)
        for option in options if current.lower() in option.lower()
    ]

# schedule works best as a slash-only command. 
# primarily because it's more practical to get the arguments from the user.
@bot.tree.command(name="schedule", description="Gets the latest schedules from the BBC services!")
@discord.app_commands.describe(sid="The channel (service ID) by it's short-name", 
                                date="The date of the schedule to get. Uses YYYY-MM-DD formatting.", 
                                page="The page of the schedule to get.",
                                region="The region of the channel.")
@discord.app_commands.autocomplete(sid=programme_sid_autocomplete,
                                    region=programme_region_autocomplete)
@discord.app_commands.rename(sid='channel')
async def programme(interaction: discord.Interaction, 
                    sid: str="BBC News [UK]", date: str=None, page: int=1, region: str=None):
    await interaction.response.defer(ephemeral=False)
    try:
        if region: sid = f"{sid} {region}"
        listing = await nitro.get_schedule(nitro_db, sid, date, page)
        items = ""
        # makes the embed base
        e = discord.Embed(title=f"Schedule for {listing['passedSid']}, {listing['date']}", 
            colour=discord.Colour.red())
        # checks which program is live, if it's a schedule from today:
        todaylive = None
        if listing['isToday']: 
            for off, i in enumerate(listing['items']):
                epochnow = int(datetime.now().timestamp())
                starttime, endtime = i['time'][0], i['time'][1]
                # if the time right now is higher than the start time 
                # *and* the endtime is higher than the start... it's live.
                if epochnow > i['time'][0] and i['time'][1] > epochnow:
                   todaylive = off 
        # sorts out every item with it's formatted date
        for off, i in enumerate(listing['items']):
            starttime = i['time'][0]
            if todaylive and off == todaylive:
                items += f"<t:{starttime}:t> - **{i['title']} (LIVE)**\n"
            else:
                items += f"<t:{starttime}:t> - {i['title']}\n"
        # adds the items field after being parsed as a single-str
        e.add_field(name=f"Page {page} (times are based on your system clock):", value=items)
        await interaction.followup.send(embed=e)
    except Exception as e:
        fansbotlog.error(traceback.format_exc())
        msg = error_template(f"```\n{e}\n```")
        m = await interaction.followup.send(embed=msg)
        return
    except:
        fansbotlog.error(traceback.format_exc())
        msg = error_template(f"<:idk:1100473028485324801> Check bot logs.")
        m = await interaction.followup.send(embed=msg)
        return

@bot.hybrid_command(name="credits", description="Thanks everyone who helped work on this bot!")
async def credits(interaction: commands.Context):
    e = discord.Embed(title="Credits", colour=discord.Colour.blurple())
    e.add_field(name="Programming", 
    value="[valbuildr](https://github.com/valbuildr)\n[slipinthedove](https://github.com/slipinthedove) (soapu64)", 
    inline=False)

    await interaction.send(embed=e, ephemeral=True)

@bot.hybrid_command(name="issue", description="Having an issue with the bot? Learn how to report it here.")
async def issue(interaction: commands.Context):
    e = discord.Embed(title="Having an issue?", 
    description="Report it on the [Github repository](https://github.com/valbuildr/bbcfansbot/issues).", 
    colour=discord.Colour.blurple())
    await interaction.send(embed=e, ephemeral=True)

bot.run(config.main_discord_token)
