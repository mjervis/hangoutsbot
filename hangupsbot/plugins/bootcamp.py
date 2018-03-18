import asyncio, logging, random, string

import hangups

import plugins

from commands import command


logger = logging.getLogger(__name__)


def _initialise(bot):
    plugins.register_admin_command(["bootcamp", "asylum", "bcadmin"])


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

        yield from bot._client.add_user(
            hangups.hangouts_pb2.AddUserRequest(
                request_header = bot._client.get_request_header(),
                invitee_id = [ hangups.hangouts_pb2.InviteeID(gaia_id = chat_id)
                               for chat_id in partial_list ],
                event_request_header = hangups.hangouts_pb2.EventRequestHeader(
                    conversation_id = hangups.hangouts_pb2.ConversationId(id = target_conv),
                    client_generated_id = bot._client.get_client_generated_id() )))

        users_added = users_added + len(partial_list)
        yield from asyncio.sleep(0.5)

    return users_added

def bcadmin(bot, event, *args):
    """Admin Bootcamp settings.
    Usage /bot bcadmin bootcamp <conversationid> - set bootcamp conversation for current hangout.
          /bot bcadmin asylum <conversationid> - set asylum conversation for current hangout.
          /bot bcadmin info - Display bootcamp/asylyum for current hangout.
    """
    
    message = ""
    
    parameters = list(args)

    if len(parameters) == 0:
        message = "<em>insufficient parameters for bcadmin</em>"
    else:
        if parameters[0] == "info":
            message = _bccheck(bot, event, *args)
        elif parameters[0] == "bootcamp":
            if len(parameters) != 2:
                message ="<em>insufficient parameters for bcadmin bootcamp</em>"
            else:
                bootcampgroupid = parameters[1]
                if _inconv(bot, bootcampgroupid):
                    _saveBootCampSetting(bot, event.conv_id, 'bootcamp', bootcampgroupid)
                    message = "<b>Bootcamp</b> Set to {}".format(bot.conversations.get_name(bootcampgroupid))
                else:
                    message = "Sorry, I'm not in that group."
        elif parameters[0] == "asylum":
            if len(parameters) != 2:
                message ="<em>insufficient parameters for bcadmin asylum</em>"
            else:
                asylumgroupid = parameters[1]
                if _inconv(bot, asylumgroupid):
                    _saveBootCampSetting(bot, event.conv_id, 'asylum', asylumgroupid)
                    message = "<b>Asylum</b> Set to {}".format(bot.conversations.get_name(asylumgroupid))
                else:
                    message = "Sorry, I'm not in that group."
    
    yield from bot.coro_send_message(event.conv_id, message)
    return { "api.response" : message }
 
  
def asylum(bot, event, *args):
    """adds user(s) into the asylum
    Usage: /bot asylum
    <user id(s)>"""
    asylumgroupid = _getBootCampSetting(bot, event.conv_id, 'asylum')
    state = ["adduser"]

    list_add = []

    for parameter in args:
        list_add.append(parameter)

    list_add = list(set(list_add))
    added = 0
    if len(list_add) > 0:
        added = yield from _batch_add_users(bot, asylumgroupid, list_add)
    
    message = "asylum: {} added to {}".format(added, asylumgroupid)
    logger.info(message)
    yield from bot.coro_send_message(event.conv_id, message)

    return { "api.response" : message }


def bootcamp(bot, event, *args):
    """gets list of users for bootcamp"""
    bootcampgroupid = _getBootCampSetting(bot, event.conv_id, 'bootcamp')

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


def _bccheck(bot, event, *args):
    bootcampgroupid = _getBootCampSetting(bot, event.conv_id, 'bootcamp')
    asylumgroupid = _getBootCampSetting(bot, event.conv_id, 'asylum')
    
    if asylumgroupid and bootcampgroupid:
        asylum_name = bot.conversations.get_name(asylumgroupid)
        bootcamp_name = bot.conversations.get_name(bootcampgroupid)
        message = "For this group:<br /><b>Bootcamp:</b> {}({}) <br /><b>Asylum:</b> {} ({})".format(bootcamp_name, bootcampgroupid, asylum_name, asylumgroupid)
    else:
        message = "Asylum and/or bootcamp unset."
        
    logger.info(message)
    
    return message


def _inconv(bot, chat_id):
    return (chat_id in bot.conversations.catalog)


def _getBootCampSetting(bot, conv_id, setting):
    # If no memory entry exists for the conversation, create it.
    if not bot.memory.exists(['conversations']):
        bot.memory.set_by_path(['conversations'],{})
    if not bot.memory.exists(['conversations',conv_id]):
        bot.memory.set_by_path(['conversations',conv_id],{})

    if bot.memory.exists(['conversations', conv_id, setting]):
        value = bot.memory.get_by_path(['conversations', conv_id, setting])
    else:
        # No path was found. Is this your first setup?
        value = 0
        
    return value


def _saveBootCampSetting(bot, conv_id, setting, value):
        # If no memory entry exists for the conversation, create it.
    if not bot.memory.exists(['conversations']):
        bot.memory.set_by_path(['conversations'],{})
    if not bot.memory.exists(['conversations',conv_id]):
        bot.memory.set_by_path(['conversations',conv_id],{})
    bot.memory.set_by_path(['conversations', conv_id, setting], value)

    bot.memory.save()