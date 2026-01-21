# bot.py
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# ================= ENV TOKEN =================
TOKEN = os.environ['TOKEN']  # safe, do not hardcode

# ================= BOT SETUP =================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATABASE =================
db = sqlite3.connect("flights.db")
cursor = db.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilot_id INTEGER,
    flight_number TEXT,
    aircraft TEXT,
    dep TEXT,
    arr TEXT,
    gate TEXT,
    altitude TEXT,
    flight_time INTEGER,
    pic TEXT,
    fo TEXT,
    crew TEXT,
    atc TEXT,
    status TEXT,
    remarks TEXT,
    timestamp TEXT
)
""")
db.commit()

# ================= KEEP-ALIVE SERVER =================
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# ================= READY EVENT =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ================= LOG FLIGHT =================
@bot.tree.command(name="logflight", description="Log a Qatar Airways PTFS flight")
async def logflight(
    interaction: discord.Interaction,
    flight_number: str,
    aircraft: str,
    dep: str,
    arr: str,
    gate: str,
    altitude: str,
    flight_time: int,
    fo: str = "N/A",
    crew: str = "N/A",
    atc: str = "N/A",
    status: str = "Completed",
    remarks: str = "Smooth"
):
    pic = interaction.user.mention
    timestamp = datetime.utcnow().strftime("%d %b %Y | %H:%M UTC")

    cursor.execute("""
    INSERT INTO flights VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        interaction.user.id,
        flight_number,
        aircraft,
        dep,
        arr,
        gate,
        altitude,
        flight_time,
        pic,
        fo,
        crew,
        atc,
        status,
        remarks,
        timestamp
    ))
    db.commit()

    embed = discord.Embed(
        title="✈️ Flight Logged Successfully",
        color=0x6a0dad
    )
    embed.add_field(name="Flight Number", value=flight_number, inline=True)
    embed.add_field(name="Aircraft", value=aircraft, inline=True)
    embed.add_field(name="Route", value=f"{dep} → {arr}", inline=False)
    embed.add_field(name="Gate", value=gate, inline=True)
    embed.add_field(name="Cruise Altitude", value=altitude, inline=True)
    embed.add_field(name="Flight Time", value=f"{flight_time} mins", inline=True)
    embed.add_field(name="Pilot-in-Command", value=pic, inline=False)
    embed.add_field(name="First Officer", value=fo, inline=False)
    embed.add_field(name="Cabin Crew", value=crew, inline=False)
    embed.add_field(name="ATC", value=atc, inline=False)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Remarks", value=remarks, inline=True)
    embed.set_footer(text=f"Logged on {timestamp}")

    await interaction.response.send_message(embed=embed)

# ================= PILOT STATS =================
@bot.tree.command(name="mystats", description="View your pilot stats")
async def mystats(interaction: discord.Interaction):
    cursor.execute(
        "SELECT COUNT(*), SUM(flight_time) FROM flights WHERE pilot_id=?",
        (interaction.user.id,)
    )
    flights, time = cursor.fetchone()
    time = time or 0

    embed = discord.Embed(
        title="👨‍✈️ Pilot Statistics",
        color=0x1abc9c
    )
    embed.add_field(name="Pilot", value=interaction.user.mention)
    embed.add_field(name="Total Flights", value=flights)
    embed.add_field(name="Total Flight Time", value=f"{time} mins")

    await interaction.response.send_message(embed=embed)

# ================= LAST FLIGHT =================
@bot.tree.command(name="lastflight", description="View your last logged flight")
async def lastflight(interaction: discord.Interaction):
    cursor.execute(
        "SELECT flight_number, aircraft, dep, arr, flight_time, timestamp FROM flights WHERE pilot_id=? ORDER BY id DESC LIMIT 1",
        (interaction.user.id,)
    )
    data = cursor.fetchone()

    if not data:
        await interaction.response.send_message("❌ No flights logged yet.")
        return

    fn, ac, dep, arr, time, ts = data

    embed = discord.Embed(
        title="🕒 Last Flight",
        color=0xf39c12
    )
    embed.add_field(name="Flight", value=fn)
    embed.add_field(name="Aircraft", value=ac)
    embed.add_field(name="Route", value=f"{dep} → {arr}")
    embed.add_field(name="Flight Time", value=f"{time} mins")
    embed.set_footer(text=f"Logged on {ts}")

    await interaction.response.send_message(embed=embed)

# ================= RUN BOT =================
bot.run(TOKEN)
