import asyncio, logging, random, string

import hangups

import plugins

from commands import command


logger = logging.getLogger(__name__)


def _initialise(bot):
    plugins.register_admin_command(["bootcamp", "asylum", "bccheck"])


@asyncio.coroutine
def _batch_add_users(bot, target_conv, chat_ids, batch_max=20):
    chat_ids = list(set(chat_ids))

    not_there = []
    for chat_id in chat_ids:
        if chat_id not in bot.conversations.catalog[target_conv]["participants"]:
            not_there.append(chat_id)
        else:
            logger.debug("addusers: user {} already in {}".format(chat_id, target_conv))
    chat_ids = not_there

    users_added = 0
    chunks = [chat_ids[i:i+batch_max] for i in range(0, len(chat_ids), batch_max)]
    for number, partial_list in enumerate(chunks):
        logger.info("batch add users: {}/{} {} user(s) into {}".format(number+1, len(chunks), len(partial_list), target_conv))
        yield from bot._client.adduser(target_conv, partial_list)
        users_added = users_added + len(partial_list)
        yield from asyncio.sleep(0.5)

    return users_added
    
def asylum(bot, event, *args):
    """adds user(s) into the asylum
    Usage: /bot asylum
    <user id(s)>"""
    asylumgroupid = bot.get_config_suboption(event.conv_id, 'asylum')
    
    list_add = []

    state = ["adduser"]

    for parameter in args:
        list_add.append(parameter)

    list_add = list(set(list_add))
    added = 0
    if len(list_add) > 0:
        added = yield from _batch_add_users(bot, asylumgroupid, list_add)
    logger.info("addusers: {} added to {}".format(added, asylumgroupid))


def bootcamp(bot, event, *args):
    """gets list of users for bootcamp"""
    bootcampgroupid = bot.get_config_suboption(event.conv_id, 'bootcamp')

    chunks = [] # one "chunk" = info for 1 hangout
    for convid, convdata in bot.conversations.get(filter=bootcampgroupid).items():
        lines = []
        lines.append('<b>{}</b>'.format(convdata["title"], len(convdata["participants"])))
        for chat_id in convdata["participants"]:
            User = bot.get_hangups_user(chat_id)
            # name and G+ link
            _line = '<b><a href="https://plus.google.com/u/0/{}/about">{}</a></b>'.format(
                User.id_.chat_id, User.full_name)
            # email from hangups UserList (if available)
            if User.emails:
                _line += '<br />... (<a href="mailto:{0}">{0}</a>)'.format(User.emails[0])
            # user id
            _line += "<br />... {}".format(User.id_.chat_id) # user id
            lines.append(_line)
        lines.append(_('<b>Users: {}</b>').format(len(convdata["participants"])))
        chunks.append('<br />'.join(lines))
    message = '<br /><br />'.join(chunks)

    yield from bot.coro_send_message(event.conv_id, message)

    return { "api.response" : message }
    
 

def bccheck(bot, event, *args):
    bootcampgroupid = bot.get_config_suboption(event.conv_id, 'bootcamp')
    asylumgroupid = bot.get_config_suboption(event.conv_id, 'asylum')
    asylum_name = bot.conversations.get_name(asylumgroupid)
    bootcamp_name = bot.conversations.get_name(bootcampgroupid)
    message = "For this group:<br /><b>Bootcamp:</b> {}({}) <br /><b>Asylum:</b> {} ({})".format(bootcamp_name, bootcampgroupid, asylum_name, asylumgroupid)
    logger.info(message)
    
    yield from bot.coro_send_message(event.conv_id, message)
    return { "api.response" : message }
 