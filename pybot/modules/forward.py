# Copyright (c) 2000-2005 Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of pybot.
# 
# pybot is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# pybot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with pybot; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from pybot.locals import *
from string import join

HELP = """
You can make me forward messages between servers and/or channels using
"forward messages [for you] [from|on|at] (user|channel) <target>]
[(from|on) server <server>] to (user|channel) <target> [on server
<server>]". You may include a string to identify the origin of the
forwarded message appending "with (server|channel [and server]|<string>)"
to the message above.
""","""
You can check what is being forwarded with "show forwards". The "forward"
permission is necessary to change or list forwards.
"""

PERM_FORWARD = """
The "forward" permission allows users to make me forward messages
between servers and/or channels, and to list what is being forwarded.
Check "help forward" for more information.
"""

class Forward:
    def __init__(self):
        db.table("forward", "fromserver text, fromtarget text, toserver text, "
                            "totarget text, flags text, with text",
                 constraints="unique (fromserver,fromtarget,"
                                     "toserver,totarget,flags)")
        hooks.register("Message", self.message_forward, 100)
        hooks.register("OutMessage", self.message_forward, 100)
        hooks.register("Notice", self.notice_forward, 100)
        hooks.register("OutNotice", self.notice_forward, 100)
        hooks.register("CTCP", self.ctcp_forward, 100)
        hooks.register("OutCTCP", self.ctcp_forward, 100)
        hooks.register("UserJoined", self.joined_forward, 100)
        hooks.register("UserParted", self.parted_forward, 100)
        hooks.register("Message", self.message)

        # forward messages [for you] [(from|on|at) [user|channel] <fromtarget>] [(from|on|at) server <fromserver>]] to [user|channel] <totarget> [(on|at) server <toserver>] [with (server|channel [and server]|<withstring>)] [!|.]
        self.re1 = regexp(r"(?P<dont>do not |don't )?forward messages (?P<foryou>for you )?(?:(?:from |on |at )(?:channel |user )?(?P<fromtarget>\S+) )?(?:(?:from |on |at )(?:server )?(?P<fromserver>\S+) )?to (?:user |channel )?(?P<totarget>\S+)(?: (?:on |at )server (?P<toserver>\S+))?(?: with (?P<withchannel>channel)?(?: and)?(?P<withserver> server)?(?P<withstring>\S+)?)?")

        # show forwards
        self.re2 = regexp(r"show forwards")

        # [message] forward[ing]
        mm.register_help("(?:message )?forward(?:ing)?", HELP, "forward")

        mm.register_perm("forward", PERM_FORWARD)
    
    def unload(self):
        hooks.unregister("Message", self.message_forward, 100)
        hooks.unregister("OutMessage", self.message_forward, 100)
        hooks.unregister("Notice", self.notice_forward, 100)
        hooks.unregister("OutNotice", self.notice_forward, 100)
        hooks.unregister("CTCP", self.ctcp_forward, 100)
        hooks.unregister("OutCTCP", self.ctcp_forward, 100)
        hooks.unregister("UserJoined", self.joined_forward, 100)
        hooks.unregister("UserParted", self.parted_forward, 100)
        hooks.unregister("Message", self.message)
        mm.unregister_help(HELP)
        mm.unregister_perm("forward")
    
    def do_forward(self, server, target, nick, forme, before, after):
        for row in db.execute("select * from forward"):
            if (row.fromserver is None or
                row.fromserver == server.servername) and \
               (row.fromtarget is None or row.fromtarget == target) and \
               (forme or "f" not in row.flags):
                fwdserver = servers.get(row.toserver)
                if fwdserver:
                    s = nick
                    if row.with.startswith(":"):
                        s = s+"@"+row.with[1:]
                    else:
                        if "c" in row.with:
                            s = s+"@"+target
                            if "s" in row.with:
                                s = s+","+server.servername
                        elif "s" in row.with:
                            s = s+"@"+server.servername
                    fwdserver.sendmsg(row.totarget, None, before+s+after,
                                      outhooks=0)
 
    def message_forward(self, msg):
        self.do_forward(msg.server, msg.target, msg.user.nick, msg.forme,
                        "<", "> "+msg.rawline)
    
    def notice_forward(self, msg):
        self.do_forward(msg.server, msg.target, msg.user.nick, msg.forme,
                        "-", "- "+msg.rawline)
    
    def ctcp_forward(self, msg):
        if msg.ctcp == "ACTION":
            self.do_forward(msg.server, msg.target, msg.user.nick, msg.forme,
                            "* ", " "+msg.rawline)
    
    def joined_forward(self, server, target, user):
        self.do_forward(server, target, user.nick, 0,
                        "--> ", " has joined")

    def parted_forward(self, server, target, user, reason):
        if reason:
            self.do_forward(server, target, user.nick, 0,
                            "--> ", " has leaved: "+reason)
        else:
            self.do_forward(server, target, user.nick, 0,
                            "--> ", " has leaved")
    
    def message(self, msg):
        if not msg.forme:
            return None

        m = self.re1.match(msg.line)
        if m:
            if mm.hasperm(msg, "forward"):
                foryou = m.group("foryou") != None
                fromtarget = m.group("fromtarget")
                fromserver = m.group("fromserver")
                totarget = m.group("totarget")
                toserver = m.group("toserver") or msg.server.servername
                withstring = m.group("withstring")
                if withstring:
                    with = ":"+withstring
                else:
                    with = ""
                    if m.group("withchannel"):
                        with += "c"
                    if m.group("withserver"):
                        with += "s"
                flags = ""
                if foryou:
                    flags += "f"
                if m.group("dont"):
                    where = []
                    wargs = []
                    if fromserver:
                        where.append("fromserver=?")
                        wargs.append(fromserver)
                    else:
                        where.append("fromserver isnull")
                    if fromtarget:
                        where.append("fromtarget=?")
                        wargs.append(fromtarget)
                    else:
                        where.append("fromtarget isnull")
                    where.extend(["toserver=?", "totarget=?",
                                  "flags=?", "with=?"])
                    wstr = " and ".join(where)
                    wargs.extend([toserver, totarget, flags, with])
                    db.execute("delete from forward where "+wstr, *wargs)
                    if not db.changed:
                        msg.answer("%:", ["Sorry, but",
                                          "Oops! I think", None],
                                         "I'm not forwarding any messages "
                                         "like this", [".", "!"])
                    else:
                        msg.answer("%:", ["Sure", "I won't forward",
                                          "Of course", "No problems"],
                                         ["!", "."])
                else:
                    try:
                        db.execute("insert into forward values (?,?,?,?,?,?)",
                                   fromserver, fromtarget, toserver,
                                   totarget, flags, with)
                        msg.answer("%:", ["Sure", "I'll forward",
                                          "Right now", "Of course"],
                                         ["!", "."])
                    except db.error:
                        msg.answer("%:", "I'm already forwarding this.")
            else:
                msg.answer("%:", ["You're not allowed to work with forwards",
                                  "Unfortunately, you can't do that",
                                  "You're not able to do that"],
                                 [".", "!"])
            return 0
        
        m = self.re2.match(msg.line)
        if m:
            if mm.hasperm(msg, "forward"):
                db.execute("select * from forward")
                if not db.results:
                    msg.answer("%:", "I'm not forwarding anything", ["!", "."])
                    return 0
                for row in db:
                    str = "I'm forwarding messages"
                    if "f" in row.flags:
                        str += " for me"
                    if row.fromserver and row.fromtarget:
                        str += " from "
                        str += row.fromtarget
                        str += " on server "
                        str += msg.fromserver
                    elif row.fromtarget:
                        str += " from "
                        str += row.fromtarget
                    elif row.fromserver:
                        str += " from server "
                        str += row.fromserver
                    str += " to "
                    str += row.totarget
                    if row.toserver and row.toserver != msg.server.servername:
                        str += " on server "
                        str += row.toserver
                    if row.with.startswith(":"):
                        str += " with "
                        str += row.with[1:]
                    elif "c" in row.with and "s" in row.with:
                        str = str+" with channel and server"
                    elif "c" in row.with:
                        str = str+" with channel"
                    elif "s" in row.with:
                        str = str+" with server"
                    msg.answer("%:", str, ".")
            else:
                msg.answer("%:", ["You're not allowed to work with forwards",
                                  "Unfortunately, you can't do that",
                                  "You're not able to do that"],
                                 [".", "!"])
            return 0
    
def __loadmodule__():
    global mod
    mod = Forward()

def __unloadmodule__():
    global mod
    mod.unload()
    del mod

# vim:ts=4:sw=4:et
