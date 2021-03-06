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
from pybot.user import User
import time
import re
import os

HELP_SEEN = """
You may check when was the last time I've seen somebody with
"[have you] seen <nick>". The "seen" or the "log" permission is
needed for this. I'll also let you know what was the last message
the user wrote, if you have the "log" permission.
"""

HELP_SEARCH = """
You may search the log files with "[show|search] (log[s]|message[s])
[with] /<regexp>/'. You must have the "log" permission for this to
work.
"""

PERM_LOG = """
The "log" permission allows users to search log messages and to ask
me what was the last time I saw somebody (like the "seen" permission).
Check "help log" and "help seen" for more information.
"""

PERM_SEEN = """
The "seen" permission allows users to ask me what was the last time I
saw somebody. Check "help seen" for more information.
"""

class LogMsg:
    def __init__(self, data):
        self.time = int(data.timestamp)
        self.servername = data.servername
        self.type = data.type
        self.src = data.src
        self.dest = data.dest
        self.line = data.line
        
    def __str__(self):
        src = User()
        src.setstring(self.src)
        if self.type == "MESSAGE":
            s = "<%s> %s" % (src.nick, self.line)
        elif self.type == "ACTION":
            s = "* %s %s" % (src.nick, self.line)
        else:
            s = ""
        return s

    def timestr(self):
        msg = time.localtime(self.time)
        now = time.localtime()
        if msg[:3] == now[:3]:
            s = "today at %d:%d" % msg[3:5]
        else:
            s = "on %d-%d-%d at %d:%d" % msg[:5]
        return s
 
STRIPNICK = re.compile(r"^[\W_]*([^\W_]+)[\W_]*$")

class Log:
    def __init__(self):
        db.table("log", "timestamp integer, servername text, type text, "
                        "nick text, src text, dest text, line text")

    def xformnick(self, nick):
        return STRIPNICK.sub(r"\1", nick.lower())

    def append(self, servername, type, nick, src, dest, line):
        nick = self.xformnick(nick)
        values = (int(time.time()), servername, type, nick, src, dest, line)
        places = ','.join(['?']*len(values))
        db.execute("insert into log values (%s)" % places, *values)

    def seen(self, nick):
        nick = self.xformnick(nick)
        row = db.execute("select * from log where nick=? and src != '' "
                         "and dest != '' order by timestamp desc limit 1",
                         nick).fetchone()
        if row:
            return LogMsg(row)
        return None

    def search(self, servername, target, regexp, max, searchline):
        p = re.compile(regexp, re.I)
        l = []
        for row in db.execute("select * from log where servername == ? and "
                              "dest == ? and src != '' order by timestamp",
                              servername, target):
            if p.search(row.line):
                l.append(LogMsg(row))
            if len(l) > max+1:
                l.pop(0)
        if l and l[-1].line == searchline:
            l.pop()
        elif len(l) > max:
            l.pop(0)
        return l

class LogModule:
    def __init__(self):
        self.log = Log()
        
        hooks.register("Message", self.message)
        hooks.register("Message", self.log_message, 150)
        hooks.register("CTCP", self.log_ctcp, 150)
        hooks.register("OutMessage", self.log_outmessage, 150)
        hooks.register("OutCTCP", self.log_outctcp, 150)

        # [have you] seen <nick>
        self.re1 = regexp(r"(?:have you )?seen (?P<nick>[^\s!?]+)", question=1)

        # [show|search] (log[s]|message[s]) [with] /<regexp>/
        self.re2 = regexp(r"(?:show |search )?(?:log|message)s? (?:with |search )?/(?P<regexp>.*)/")

        # seen
        mm.register_help("seen", HELP_SEEN, "seen")

        # log|(search|show) (log[s]|message[s])
        mm.register_help("log|(?:search|show) (?:log|message)s?",
                         HELP_SEARCH, "log")

        mm.register_perm("seen", PERM_SEEN)
        mm.register_perm("log", PERM_LOG)
        
    def unload(self):
        hooks.unregister("Message", self.message)
        hooks.unregister("Message", self.log_message, 150)
        hooks.unregister("CTCP", self.log_ctcp, 150)
        hooks.unregister("OutMessage", self.log_outmessage, 150)
        hooks.unregister("OutCTCP", self.log_outctcp, 150)
        mm.unregister_help(HELP_SEEN)
        mm.unregister_help(HELP_SEARCH)
        mm.unregister_perm("seen")
        mm.unregister_perm("log")
    
    def message(self, msg):
        if msg.forme:
            m = self.re1.match(msg.line)
            if m:
                if mm.hasperm(msg, "seen") or \
                   mm.hasperm(msg, "log"):
                    nick = m.group("nick")
                    logmsg = self.log.seen(nick)
                    if not logmsg:
                        msg.answer("%:", "Sorry, I haven't seen %s for a while..." % nick)
                    elif mm.hasperm(msg, "log") and msg.target == logmsg.dest:
                        msg.answer("%:", "I have seen %s %s, with the "
                                         "following message:" %
                                         (nick, logmsg.timestr()))
                        msg.answer(str(logmsg))
                    else:
                        msg.answer("%:", "I have seen %s %s." %
                                         (nick, logmsg.timestr()))
                    return 0
                else:
                    msg.answer("%:", "You're not",
                                     ["allowed to know when was the "
                                      "last time I saw somebody",
                                      "that good", "allowed to do this"],
                                     [".", "!"])
                return 0

            m = self.re2.match(msg.line)
            if m:
                if mm.hasperm(msg, "log"):
                    max = 5
                    logmsgs = self.log.search(msg.server.servername,
                                              msg.target,
                                              m.group("regexp"), max,
                                              msg.rawline)
                    if logmsgs:
                        llen = len(logmsgs)
                        if llen == 1:
                            if max == 1:
                                s = "Here is the last entry found:"
                            else:
                                s = "Here is the only entry found:"
                        elif llen == max:
                            s = "Here are the last %d entries found:" % llen
                        else:
                            s = "Here are the only %d entries found:" % llen
                        msg.answer("%:", s)
                        for logmsg in logmsgs:
                            msg.answer(str(logmsg))
                    else:
                        msg.answer("%:", ["Sorry!", "Oops!"],
                                         ["No messages found",
                                          "Can't find any message",
                                          "No entries found"], [".", "!"])
                else:
                    msg.answer("%:", [("You're not",
                                       ["allowed to search logs",
                                        "that good",
                                        "allowed to do this"]),
                                      "No", "Nope"],
                                     [".", "!"])
                return 0
    
    def log_message(self, msg):
        if msg.direct:
            target = ""
        else:
            target = msg.target
        self.log.append(msg.server.servername, "MESSAGE", msg.user.nick,
                        msg.user.string, target, msg.rawline)
    
    def log_ctcp(self, msg):
        if msg.ctcp == "ACTION":
            if msg.direct:
                target = ""
            else:
                target = msg.target
            self.log.append(msg.server.servername, "ACTION", msg.user.nick,
                            msg.user.string, target, msg.rawline)

    def log_outmessage(self, msg):
        self.log.append(msg.server.servername, "MESSAGE", "", "",
                        msg.target, msg.rawline)
    
    def log_outctcp(self, msg):
        if msg.ctcp == "ACTION":
            self.log.append(msg.server.servername, "ACTION", "", "",
                            msg.target, msg.rawline)

def __loadmodule__():
    global mod
    mod = LogModule()

def __unloadmodule__():
    global mod
    mod.unload()
    del mod

# vim:ts=4:sw=4:et
