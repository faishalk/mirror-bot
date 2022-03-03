import itertools

from requests import get as rget
from time import sleep
from threading import Thread
from html import escape
from urllib.parse import quote
from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import dispatcher, LOGGER, SEARCH_API_LINK, SEARCH_PLUGINS, get_client
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage, sendMarkup, auto_delete_message
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import get_readable_file_size
from bot.helper.telegram_helper import button_build

if SEARCH_PLUGINS is not None:
    PLUGINS = []
    qbclient = get_client()
    qb_plugins = qbclient.search_plugins()
    if qb_plugins:
        for plugin in qb_plugins:
            qbclient.search_uninstall_plugin(names=plugin['name'])
    qbclient.search_install_plugin(SEARCH_PLUGINS)
    qbclient.auth_log_out()

SITES = {
    "1337x": "1337x",
    "yts": "YTS",
    "eztv": "EzTv",
    "tgx": "TorrentGalaxy",
    "torlock": "Torlock",
    "piratebay": "PirateBay",
    "nyaasi": "NyaaSi",
    "rarbg": "Rarbg",
    "ettv": "Ettv",
    "zooqle": "Zooqle",
    "kickass": "KickAss",
    "bitsearch": "Bitsearch",
    "glodls": "Glodls",
    "magnetdl": "MagnetDL",
    "limetorrent": "LimeTorrent",
    "torrentfunk": "TorrentFunk",
    "torrentproject": "TorrentProject",
    "all": "All"
}

SEARCH_LIMIT = 300


def torser(update, context):
    user_id = update.message.from_user.id
    try:
        key = update.message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        smsg = sendMessage("ℹ️ Ketik sebuah keyword untuk memulai pencarian!", context.bot, update.message)
        Thread(target=auto_delete_message, args=(context.bot, update.message, smsg)).start()
        return
    if SEARCH_API_LINK is not None and SEARCH_PLUGINS is not None:
        buttons = button_build.ButtonMaker()
        buttons.sbutton('Api', f"torser {user_id} api")
        buttons.sbutton('Plugins', f"torser {user_id} plugin")
        buttons.sbutton("Cancel", f"torser {user_id} cancel")
        button = InlineKeyboardMarkup(buttons.build_menu(2))
        sendMarkup('Pilih opsi pencarian:', context.bot, update.message, button)
    elif SEARCH_API_LINK is not None and SEARCH_PLUGINS is None:
        button = _api_buttons(user_id)
        sendMarkup('Pilih website pencarian:', context.bot, update.message, button)
    elif SEARCH_API_LINK is None and SEARCH_PLUGINS is not None:
        button = _plugin_buttons(user_id)
        sendMarkup('Pilih website pencarian:', context.bot, update.message, button)
    else:
        return sendMessage("No API link or search PLUGINS added for this function", context.bot, update.message)

def torserbut(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(" ", maxsplit=1)[1]
    data = query.data
    data = data.split(" ")
    if user_id != int(data[1]):
        query.answer(text="Bukan buat elu!", show_alert=True)
    elif data[2] == 'api':
        query.answer()
        button = _api_buttons(user_id)
        editMessage('Pilih website pencarian:', message, button)
    elif data[2] == 'plugin':
        query.answer()
        button = _plugin_buttons(user_id)
        editMessage('Pilih website pencarian:', message, button)
    elif data[2] != "cancel":
        query.answer()
        site = data[2]
        tool = data[3]
        if tool == 'api':
            editMessage(f"<b>Sedang mencari torrent <code>{key}</code>\nTorrent Site:- <i>{SITES.get(site)}</i></b>", message)
        else:
            editMessage(f"<b>Sedang mencari torrent <code>{key}</code>\nTorrent Site:- <i>{site.capitalize()}</i></b>", message)
        Thread(target=_search, args=(key, site, message, tool)).start()
    else:
        query.answer()
        editMessage(f"ℹ️ <b>Pencarian torrent <code>{key}</code> dibatalkan!</b>", message)

def _search(key, site, message, tool):
    LOGGER.info(f"Searching: {key} from {site}")
    if tool == 'api':
        api = f"{SEARCH_API_LINK}/api/{site}/{key}"
        try:
            resp = rget(api)
            search_results = resp.json()
            if site == "all":
                search_results = list(itertools.chain.from_iterable(search_results))
            if isinstance(search_results, list):
                msg = f"<b>Hasil pencarian:</b> <code>{key}</code>\n"
                msg += f"<b>Ditemukan: <u>{min(len(search_results), SEARCH_LIMIT)} hasil</u>\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
            else:
                return editMessage(f"ℹ️ Tidak ada torrent yang cocok dengan <code>{key}</code>\nTorrent Site:- <i>{SITES.get(site)}</i>", message)
        except Exception as e:
            editMessage(f"⚠️ {e}", message)
    else:
        client = get_client()
        search = client.search_start(pattern=str(key), plugins=str(site), category='all')
        search_id = search.id
        while True:
            result_status = client.search_status(search_id=search_id)
            status = result_status[0].status
            if status != 'Running':
                break
        dict_search_results = client.search_results(search_id=search_id)
        search_results = dict_search_results.results
        total_results = dict_search_results.total
        if total_results != 0:
            msg = f"<b>Hasil pencarian:</b> <code>{key}</code>\n"
            msg += f"<b>Ditemukan: <u>{min(len(search_results), SEARCH_LIMIT)} hasil</u>\nTorrent Site:- <i>{site.capitalize()}</i></b>"
        else:
            return editMessage(f"ℹ️ Tidak ada torrent yang cocok dengan <code>{key}</code>\nTorrent Site:- <i>{site.capitalize()}</i>", message)
    link = _getResult(search_results, key, message, tool)
    buttons = button_build.ButtonMaker()
    buttons.buildbutton("🔎 Hasil Pencarian", link)
    button = InlineKeyboardMarkup(buttons.build_menu(1))
    editMessage(msg, message, button)
    if tool != 'api':
        client.search_delete(search_id=search_id)

def _getResult(search_results, key, message, tool):
    telegraph_content = []
    msg = f"<h4>Search Result For {key}</h4>"
    for index, result in enumerate(search_results, start=1):
        msg += "<br>"
        if tool == 'api':
            try:
                msg += f"<code><a href='{result['Url']}'>{escape(result['Name'])}</a></code><br>"
                if "Category" in result.keys():
                    msg += f"<b>Category: </b><code>{result['Category']}</code><br>"
                if "Files" in result.keys():
                    for subres in result['Files']:
                        msg += f"<b>Quality: </b>{subres['Quality']} | <b>Size: </b>{subres['Size']}<br>"
                        try:
                            msg += f"<b>Share Direct Link to</b> <a href='http://t.me/share/url?url={quote(subres['Torrent'])}'>Telegram</a><br>"
                        except KeyError:
                            msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={subres['Magnet']}'>Telegram</a><br>"
                else:
                    msg += f"<b>Size: </b>{result['Size']}<br>"
                    msg += f"<b>Seeders: </b>{result['Seeders']} | <b>Leechers: </b>{result['Leechers']}<br>"
            except KeyError:
                pass
            try:
                msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(result['Magnet'])}'>Telegram</a><br>"
            except KeyError:
                pass
            try:
                msg += f"<b>Share Direct Link to</b> <a href='http://t.me/share/url?url={quote(result['Torrent'])}'>Telegram</a><br>"
            except KeyError:
                pass
        else:
            msg += f"<code><a href='{result.descrLink}'>{escape(result.fileName)}</a></code><br>"
            msg += f"<b>Size: </b>{get_readable_file_size(result.fileSize)}<br>"
            msg += f"<b>Seeders: </b>{result.nbSeeders} | <b>Leechers: </b>{result.nbLeechers}<br>"
            link = result.fileUrl
            if link.startswith('magnet:'):
                msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(link)}'>Telegram</a><br>"
            else:
                msg += f"<b>Share Url to</b> <a href='http://t.me/share/url?url={link}'>Telegram</a><br>"

        if len(msg.encode('utf-8')) > 39000:
           telegraph_content.append(msg)
           msg = ""

        if index == SEARCH_LIMIT:
            break

    if msg != "":
        telegraph_content.append(msg)

    editMessage(f"<b>Creating</b> {len(telegraph_content)} <b>Telegraph pages.</b>", message)
    path = [telegraph.create_page(
                title='Mirror-in Torrent Search',
                content=content
            )["path"] for content in telegraph_content]
    sleep(0.5)
    if len(path) > 1:
        editMessage(f"<b>Editing</b> {len(telegraph_content)} <b>Telegraph pages.</b>", message)
        _edit_telegraph(path, telegraph_content)
    return f"https://telegra.ph/{path[0]}"

def _edit_telegraph(path, telegraph_content):
    nxt_page = 1
    prev_page = 0
    num_of_path = len(path)
    for content in telegraph_content :
        content += "<br>"
        if nxt_page == 1 :
            content += f'<b><a href="https://telegra.ph/{path[nxt_page]}">Next</a></b>'
            nxt_page += 1
        else :
            if prev_page <= num_of_path:
                content += f'<b><a href="https://telegra.ph/{path[prev_page]}">Prev</a></b>'
                prev_page += 1
            if nxt_page < num_of_path:
                content += f'<b> | <a href="https://telegra.ph/{path[nxt_page]}">Next</a></b>'
                nxt_page += 1
        telegraph.edit_page(
            path = path[prev_page],
            title = 'Mirror-in Torrent Search',
            content=content
        )
    return

def _api_buttons(user_id):
    buttons = button_build.ButtonMaker()
    for data, name in SITES.items():
        buttons.sbutton(name, f"torser {user_id} {data} api")
    buttons.sbutton("Cancel", f"torser {user_id} cancel")
    button = InlineKeyboardMarkup(buttons.build_menu(2))
    return button

def _plugin_buttons(user_id):
    buttons = button_build.ButtonMaker()
    if not PLUGINS:
        qbclient = get_client()
        pl = qbclient.search_plugins()
        for name in pl:
            PLUGINS.append(name['name'])
        qbclient.auth_log_out()
    for siteName in PLUGINS:
        buttons.sbutton(siteName.capitalize(), f"torser {user_id} {siteName} plugin")
    buttons.sbutton('All', f"torser {user_id} all plugin")
    buttons.sbutton("Cancel", f"torser {user_id} cancel")
    button = InlineKeyboardMarkup(buttons.build_menu(2))
    return button


torser_handler = CommandHandler(BotCommands.SearchCommand, torser, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
torserbut_handler = CallbackQueryHandler(torserbut, pattern="torser", run_async=True)

dispatcher.add_handler(torser_handler)
dispatcher.add_handler(torserbut_handler)
