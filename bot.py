import asyncio
import os
import discord
import logging

from dotenv import load_dotenv
from datetime import datetime, time
from zoneinfo import ZoneInfo
from discord.ext import tasks
from pathlib import Path
from config.logging_config import configure_logging

from briefing import make_briefing, shorten_description
from cves import get_relevant_cves
from ai_ranking import get_ai_ranked_articles
from feeds import check_all_feeds_once
from database import get_todays_quiz, initialize_database
from quiz_generation import generate_and_save_quiz

load_dotenv()
configure_logging()
initialize_database()

logger = logging.getLogger(__name__)

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN saknas. Lägg till den i .env-filen.")

BOT_ENV = os.getenv("BOT_ENV", "production").lower()
IS_TEST = BOT_ENV == "test"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

MORNING_TIME = time(
    hour=8,
    minute=0,
    tzinfo=ZoneInfo("Europe/Stockholm"),
)

EVENING_TIME = time(
    hour=20,
    minute=0,
    tzinfo=ZoneInfo("Europe/Stockholm"),
)

QUIZ_TIME = time(
    hour=8,
    minute=0,
    tzinfo=ZoneInfo("Europe/Stockholm"),
)


async def create_briefing_message(period):
    articles, ai_ranked = await asyncio.to_thread(get_ai_ranked_articles)
    cves = await get_relevant_cves()

    return make_briefing(articles, cves[:3], period, ai_ranked)


async def send_scheduled_briefing(period):
    now = datetime.now(ZoneInfo("Europe/Stockholm"))

    if now.weekday() >= 5:
        logger.info("Hoppar över %s-briefing: helg.", period)
        return

    await client.wait_until_ready()

    channel_ids = [
        int(value.strip())
        for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]

    if not channel_ids:
        raise RuntimeError("No briefing channels are configured.")

    message = await create_briefing_message(period)

    for channel_id in channel_ids:
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)

        await channel.send(message, suppress_embeds=True)

    return len(channel_ids)


async def run_scheduled_briefing(period):
    try:
        logger.info("Starting %s scheduled briefing.", period)
        sent_channel_count = await send_scheduled_briefing(period)
    except Exception:
        logger.exception("Scheduled %s briefing failed.", period)
    else:
        logger.info(
            "Scheduled %s briefing sent to %d channel(s).",
            period,
            sent_channel_count,
        )


async def send_scheduled_quiz():
    await client.wait_until_ready()

    channel_id = os.getenv("QUIZ_CHANNEL_ID", "").strip()
    if not channel_id:
        raise RuntimeError("QUIZ_CHANNEL_ID is not configured.")

    course_name = os.getenv("CYBERBEAR_COURSE_NAME", "").strip()
    course_plan_ref = os.getenv("CYBERBEAR_COURSE_PLAN_REF", "").strip()
    if not course_name or not course_plan_ref:
        raise RuntimeError(
            "CYBERBEAR_COURSE_NAME and CYBERBEAR_COURSE_PLAN_REF must be configured."
        )

    quiz_date = datetime.now(ZoneInfo("Europe/Stockholm")).date().isoformat()
    await asyncio.to_thread(
        generate_and_save_quiz,
        quiz_date,
        course_name,
        course_plan_ref,
    )
    quiz = await asyncio.to_thread(get_todays_quiz, quiz_date)

    if quiz is None:
        raise RuntimeError(
            f"Quiz generation did not produce a saved quiz for {quiz_date}.")

    questions = [
        {
            **question,
            "options": [
                (option["option_text"], option["is_correct"])
                for option in question["options"]
            ],
        }
        for question in quiz["questions"]
    ]
    if len(questions) != 3:
        raise ValueError(
            f"Quiz for {quiz_date} has {len(questions)} questions; expected exactly 3."
        )

    channel = client.get_channel(int(channel_id))
    if channel is None:
        channel = await client.fetch_channel(int(channel_id))

    await channel.send(
        f"## Dagens quiz — {quiz_date}\nTryck på knappen för att starta!",
        view=StartQuizView(questions),
    )
    return quiz_date


async def run_scheduled_quiz():
    try:
        logger.info("Starting scheduled quiz.")
        quiz_date = await send_scheduled_quiz()
    except Exception:
        logger.exception("Scheduled quiz failed.")
    else:
        logger.info("Scheduled quiz for %s was posted.", quiz_date)


@tasks.loop(time=MORNING_TIME)
async def scheduled_morning_briefing():
    await run_scheduled_briefing("morning")


@tasks.loop(time=QUIZ_TIME)
async def scheduled_quiz():
    await run_scheduled_quiz()


@tasks.loop(time=EVENING_TIME)
async def scheduled_evening_briefing():
    await run_scheduled_briefing("evening")


async def send_feed_message(message):
    channel_ids = [
        int(value.strip())
        for value in os.getenv("BRIEFING_CHANNEL_IDS", "").split(",")
        if value.strip()
    ]

    if not channel_ids:
        raise RuntimeError("No briefing channels are configured.")

    for channel_id in channel_ids:
        channel = client.get_channel(channel_id)

        if channel is None:
            channel = await client.fetch_channel(channel_id)

        await channel.send(message, suppress_embeds=True)


@tasks.loop(minutes=10)
async def scheduled_feed_check():
    try:
        posted_count = await check_all_feeds_once(send_feed_message)
        logger.info("Feed check completed; posted %d article(s).", posted_count)
    except Exception:
        logger.exception("Scheduled feed check failed.")


@scheduled_feed_check.before_loop
async def before_check_feeds():
    await client.wait_until_ready()


@client.event
async def on_ready():
    try:
        synced = await tree.sync()
    except Exception:
        logger.exception("Failed to sync application commands.")
    else:
        logger.info("Synced %d global application command(s).", len(synced))

    logger.info("Logged in as %s.", client.user)

    # if IS_TEST:
    #     logger.info("Test environment: automatic scheduled jobs are disabled.")
    #     return

    if not scheduled_morning_briefing.is_running():
        scheduled_morning_briefing.start()

    if not scheduled_quiz.is_running():
        scheduled_quiz.start()

    if not scheduled_evening_briefing.is_running():
        scheduled_evening_briefing.start()

    if not scheduled_feed_check.is_running():
        scheduled_feed_check.start()


@tree.command(name="brief", description="Få en briefing på nyheter inom cybersäkerhet från Cyberbear.")
async def brief(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    message = await create_briefing_message("other")

    await interaction.followup.send(message, suppress_embeds=True)


@tree.command(name="check_feeds", description="Kontrollera nyhets-flöden nu.")
async def check_feeds_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    new_articles = await check_all_feeds_once(send_feed_message)

    if new_articles:
        await interaction.followup.send(
            f"Feed-kontrollen är klar. Skickade {new_articles} ny(a) artikel/artiklar.",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            "Det finns inga nya artiklar. <:sadge:1568301148895584363>",
            ephemeral=True,
        )


@tree.command(name="check_cve", description="Kolla nya CVEr.")
async def check_cve(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    cves = await get_relevant_cves()

    lines = [
        "## 🛡️  Nya sårbarheter:"
    ]

    for cve in cves[:3]:
        lines.append(f"### {cve['id']}")
        lines.append(
            f"**Allvarlighetsgrad:** {cve['severity']}, {cve['score']}")

        description = shorten_description(cve['description'])
        lines.append(description)

        lines.append(
            f"[Läs mer](https://nvd.nist.gov/vuln/detail/{cve['id']})")
        lines.append("")

    await interaction.followup.send(
        "\n".join(lines),
        suppress_embeds=True,
        ephemeral=True,
    )


class QuizAnswerButton(discord.ui.Button):
    def __init__(self, quiz_view, option_index):
        self.quiz_view = quiz_view
        self.option_index = option_index
        label = chr(ord("A") + option_index)
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=option_index // 5,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.quiz_view.submit_answer(interaction, self.option_index)


class QuizSessionView(discord.ui.View):
    def __init__(self, questions, user_id):
        super().__init__(timeout=900)
        self.questions = questions
        self.user_id = user_id
        self.question_index = 0
        self.answers = []
        self.add_answer_buttons()

    def add_answer_buttons(self):
        question = self.questions[self.question_index]
        for option_index in range(len(question["options"])):
            self.add_item(QuizAnswerButton(self, option_index))

    def render_question(self):
        question = self.questions[self.question_index]
        choices = [
            f"**{chr(ord('A') + index)}.** {option_text}"
            for index, (option_text, _) in enumerate(question["options"])
        ]
        return (
            f"**Fråga {self.question_index + 1}/{len(self.questions)}**\n"
            f"{question['question_text']}\n\n"
            f"{chr(10).join(choices)}"
        )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Det här quizet tillhör någon annan.",
                ephemeral=True,
            )
            return False
        return True

    async def submit_answer(
        self,
        interaction: discord.Interaction,
        selected_index: int,
    ):
        question = self.questions[self.question_index]
        self.answers.append(selected_index)
        _, is_correct = question["options"][selected_index]
        correct_index = next(
            index
            for index, (_, option_is_correct) in enumerate(question["options"])
            if option_is_correct
        )
        correct_text = question["options"][correct_index][0]

        if is_correct:
            feedback = "✅ Rätt svar!"
        else:
            feedback = f"❌ Inte riktigt. Rätt svar: **{chr(ord('A') + correct_index)}. {correct_text}**"

        feedback += f"\n*Förklaring:* {question['explanation']}"
        self.question_index += 1

        if self.question_index == len(self.questions):
            summary = ["## Quizet är klart! Här är sammanfattningen:"]
            for index, (answered_question, answer_index) in enumerate(
                zip(self.questions, self.answers),
                start=1,
            ):
                correct_index = next(
                    option_index
                    for option_index, (_, option_is_correct) in enumerate(
                        answered_question["options"]
                    )
                    if option_is_correct
                )
                correct_text = answered_question["options"][correct_index][0]
                player_text = answered_question["options"][answer_index][0]
                result = "✅" if answer_index == correct_index else "❌"
                summary.extend(
                    [
                        f"## Fråga {index}\n**{answered_question['question_text']}**\n",
                        f"Ditt svar: {chr(ord('A') + answer_index)}. {player_text}",
                        f"Rätt svar: {chr(ord('A') + correct_index)}. {correct_text} {result}\n",
                        f"*Förklaring:* {answered_question['explanation']}",
                        "",
                    ]
                )

            summary_text = "\n".join(summary)
            summary_chunks = []
            while len(summary_text) > 1900:
                split_at = summary_text.rfind("\n", 0, 1900)
                if split_at == -1:
                    split_at = 1900
                summary_chunks.append(summary_text[:split_at])
                summary_text = summary_text[split_at:].lstrip()
            summary_chunks.append(summary_text)

            await interaction.response.edit_message(
                content=summary_chunks[0],
                view=None,
            )
            for chunk in summary_chunks[1:]:
                await interaction.followup.send(chunk, ephemeral=True)
            return

        self.clear_items()
        self.add_answer_buttons()
        await interaction.response.edit_message(
            content=f"{feedback}\n\n{self.render_question()}",
            view=self,
        )


class StartQuizView(discord.ui.View):
    def __init__(self, questions):
        super().__init__(timeout=3600)
        self.questions = questions

    @discord.ui.button(
        label="Start Quiz",
        style=discord.ButtonStyle.primary,
        custom_id="cyberbear:test-quiz-start",
    )
    async def start_quiz(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        session = QuizSessionView(self.questions, interaction.user.id)
        await interaction.response.send_message(
            session.render_question(),
            view=session,
            ephemeral=True,
        )


# --------------------
# FOR TESTING PURPOSES
if IS_TEST:
    @tree.command(name="preview_svt", description="Visa SVT-artiklar som filtret väljer.")
    async def preview_svt(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        entries = await asyncio.to_thread(get_svt_articles)
        matches = await asyncio.to_thread(filter_svt_articles, entries)

        if not matches:
            await interaction.followup.send(
                f"Hämtade {len(entries)} artiklar från SVT, men filtret hittade inga träffar.",
                ephemeral=True,
            )
            return

        lines = ["**SVT-träffar i det aktuella flödet:**"]

        for article in matches[:10]:
            title = article.get("title", "Artikel utan rubrik")
            link = article.get("link", "")
            lines.append(f"• [{title}]({link})")

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @tree.command(name="test", description="test")
    async def test(interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")

    @tree.command(
        name="test_quiz",
        description="Visa det förgenererade quizet för idag."
    )
    async def test_quiz(interaction: discord.Interaction):
        owner_user_id = os.getenv("OWNER_USER_ID")
        if not owner_user_id or str(interaction.user.id) != owner_user_id:
            await interaction.response.send_message(
                "Du har inte behörighet att köra detta test.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            quiz_date = datetime.now(
                ZoneInfo("Europe/Stockholm")
            ).date().isoformat()
            quiz = await asyncio.to_thread(get_todays_quiz, quiz_date)

            if quiz is None:
                await interaction.followup.send(
                    f"Det finns inget sparat quiz för {quiz_date} ännu.",
                    ephemeral=True,
                )
                return

            questions = [
                {
                    **question,
                    "options": [
                        (option["option_text"], option["is_correct"])
                        for option in question["options"]
                    ],
                }
                for question in quiz["questions"]
            ]

            if len(questions) != 3:
                await interaction.followup.send(
                    f"Quizet för {quiz_date} har {len(questions)} frågor; förväntade 3.",
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                f"Dagens sparade testquiz ({quiz_date}) är redo. Klicka för att starta:",
                view=StartQuizView(questions),
            )

        except Exception:
            logger.exception("Discord test quiz command failed.")
            await interaction.followup.send(
                "Quiztestet misslyckades. Se botloggen för detaljer.",
                ephemeral=True,
            )


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError,
):
    command_name = interaction.command.name if interaction.command else "unknown"

    original_error = (
        error.original
        if isinstance(error, discord.app_commands.CommandInvokeError)
        else error
    )

    logger.error(
        "Command /%s failed: %s",
        command_name,
        original_error,
        exc_info=(
            type(original_error),
            original_error,
            original_error.__traceback__,
        ),
    )

    message = "Something went wrong while Cyberbear was running that command."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


client.run(token)
