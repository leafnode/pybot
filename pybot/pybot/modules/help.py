# Copyright (c) 2000-2001 Gustavo Niemeyer <niemeyer@conectiva.com>
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

from pybot import hooks, mm, options
import re

HELP = [
("""\
You may ask for help using "[show] help [about] <keyword>".\
""",)
]

class Help:
	def __init__(self, bot):
		self.data = options.getsoft("Help.data", {})
		mm.register("register_help", self.mm_register_help)
		mm.register("unregister_help", self.mm_unregister_help)
		hooks.register("Message", self.message)
		
		# [show] help [about] <keyword>
		self.re1 = re.compile(r"(?:show\s+)?help(?:\s+about)?(?:\s+(?P<keyword>\S+))?\s*[.!]*$", re.I)
		
	def unload(self):
		hooks.unregister("Message", self.message)
		mm.unregister("register_help")
		mm.unregister("unregister_help")
	
	def message(self, msg):
		if msg.forme:
			m = self.re1.match(msg.line)
			if m:
				if mm.hasperm(0, msg.server.servername, msg.target, msg.user, "help"):
					keyword = m.group("keyword")
					if keyword:
						text = self.data.get(keyword)
					else:
						text = HELP
					if text:
						for line in text:
							msg.answer("%:", *line)
					else:
						msg.answer("%:", ["No", "Sorry, no", "Sorry, but there's no"], "help about that", [".", "!"])
				else:
					msg.answer("%:", ["Sorry, you", "You"], ["can't", "are not allowed to"], "ask for help", [".", "!"])
				return 0
			
	def mm_register_help(self, defret, keywords, text):
		for keyword in keywords:
			self.data[keyword] = text

	def mm_unregister_help(self, defret, keywords):
		for keyword in keywords:
			try: 
				del self.data[keyword]
			except KeyError:
				pass

def __loadmodule__(bot):
	global help
	help = Help(bot)

def __unloadmodule__(bot):
	global help
	help.unload()
	del help

# vim:ts=4:sw=4:nowrap
