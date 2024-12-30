import readline
import subprocess
import traceback
from dataclasses import dataclass
from typing import Callable, List, Dict
from .utils import split_command, command_groups
from .schemacontext import SchemaContext


RUNNING_PIPE_CMDS_DICT = {
 "append" : "Append output text to a file",
 "begin" : "Begin with the line that matches",
 "context-match" : "Context match",
 "count" : "Count the number of lines in the output",
 "csv" : "Show table output in CSV format",
 "de-select" : "De-select columns",
 "details" : "Display default values",
 "display" : "Display options",
 "exclude" : "Exclude lines that match",
 "extended" : "Display referring entries",
 "icount" : "Count the number of matching instances",
 "include" : "Include lines that match",
 "linnum" : "Enumerate lines in the output",
 "more" : "Paginate output",
 "nomore" : "Suppress pagination",
 "save" : "Save output text to a file",
 "select" : "Select additional columns",
 "tab" : "Enforce table output",
 "until" : "End with the line that matches"
}

@dataclass
class CommandAction:
    name: str
    help: str
    action: Callable[[List[str]], None] = None
    complete: Callable[[List[str]], Dict[str, str]] = None
    children: "List[CommandAction]" = None



class InputError(Exception):
    pass


class CliContext:
    # modes
    NORMAL = 1
    CONFIG = 2

    def __init__(self, sc: "SchemaContext"):
        self.mode = self.NORMAL
        self._completed_options = None
        self.long_help = True
        self.path = []  # current context path
        self.sc = sc    # schema context
        self.normal_mode_actions = CommandAction(
            name="normal",
            help="Fallback handler in nromal mode",
            action=self.normal_mode_action,
            complete=self.normal_mode_complete,
            children=[
                CommandAction(
                    name="show",
                    help="Show ",
                    action=self.normal_mode_show_action,
                    complete=self.normal_mode_show_complete,
                    children=[
                        CommandAction(
                            name="running-config",
                            help="Show running configuration",
                            action=self.normal_mode_show_running_config_action,
                            complete=self.normal_mode_show_running_config_complete,
                        ),
                    ]
                ),
                CommandAction(
                    name="config",
                    help="Enter config mode",
                    action=self.normal_mode_config_action,
                ),
                CommandAction(
                    name="exit",
                    help="Exit from current mode",
                    action=self.normal_mode_exit_action,
                )
            ]
        )
        self.config_mode_actions = CommandAction(
            name="config",
            help="Fallback handler in config mode",
            action=self.config_mode_action,
            complete=self.config_mode_complete,
            children=[
                CommandAction(
                    name="exit",
                    help="Exit from current mode",
                    action=self.config_mode_exit_action,
                ),
                CommandAction(
                    name="end",
                    help="Exit config mode",
                    action=self.config_mode_end_action,
                ),
                # command `top`
                CommandAction(
                    name="top",
                    help="Return to top level",
                    action=self.config_mode_top_action,
                ),
                # command `show`
                CommandAction(
                    name="show",
                    help="Show ",
                    action=self.config_mode_show_action,
                    complete=self.config_mode_show_complete,
                ),
                # command `do`
                CommandAction(
                    name="do",
                    help="Execute command",
                    action=self.config_mode_do_action,
                    complete=self.config_mode_do_complete,
                ),
                # command `no`
                CommandAction(
                    name="no",
                    help="Negate command",
                    action=self.config_mode_no_action,
                    complete=self.config_mode_no_complete,
                ),
            ]
        )
    
    def execute(self, line: "str|list[str]"):
        if isinstance(line, list):
            items = line
        else:
            items = split_command(line)
        if not items:
            return
        # split items with ';'
        groups = command_groups(items)
        for items in groups:
            last_command = self.normal_mode_actions
            if self.mode == self.CONFIG:
                last_command = self.config_mode_actions
            tree = last_command.children
            for index, item in enumerate(items):
                commands = [x for x in tree if x.name.startswith(item)]
                if len(commands) == 0:
                    break
                if len(commands) > 1:
                    raise InputError(f"ambiguous command {item}, matches are {[x['command'] for x in commands]}")
                else:
                    # exactly 1 match
                    # fill the full command in item
                    last_command = commands[0]
                    items[index] = last_command.name
                    if not commands[0].children:
                        break
                    tree = commands[0].children
            if last_command:
                last_command.action(items)
    def get_available_commands(self, prefix: "str|list[str]") -> "dict[str,str]":
        if isinstance(prefix, list):
            items = prefix
        else:
            items = prefix.split()
        last_command = self.normal_mode_actions
        if self.mode == self.CONFIG:
            last_command = self.config_mode_actions
        tree = last_command.children
        all_items_used = True
        for index, item in enumerate(items):
            commands = [x for x in tree if x.name.startswith(item)]
            if len(commands) == 0:
                all_items_used = False
                break
            if len(commands) != 1:
                return {}
            else:
                # exactly 1 match
                if not commands[0].children:
                    last_command = commands[0]
                    all_items_used = False
                    break
                last_command = commands[0]
                items[index] = last_command.name
                tree = commands[0].children
        if tree:
            if all_items_used:
                actions = {x.name: x.help for x in tree}
            else:
                actions = {}
        if last_command and last_command.complete:
            extra_items = last_command.complete(items)
            actions.update(extra_items)
        return actions
    
    def get_prompt(self):
        demo = "demo"
        if self.mode == self.CONFIG:
            if self.path:
                #path = '/'.join(str(x) for x in self.path)
                path = ""
                for item in self.path:
                    if item.name in ["config", "system", "interfaces"]:
                        continue
                    path += f"-{item.name}"
                    # if item.typ == ContextNode.LIST and item.key_val:
                    #     path += f"-{item.key_val}"
                return f"{demo}(config{path})# "
            return f"{demo}(config)# "
        return f"{demo}# "


    def complete(self, text: str, state: int):
        try:
            #print(f"In complete: text={text}, state={state}")
            # get current line
            if state == 0:
                # simple cache
                idx = readline.get_begidx()
                full = readline.get_line_buffer()
                #print(f" full={full}")

                if '|' in full:
                    options = {k: v for k, v in RUNNING_PIPE_CMDS_DICT.items() if k.startswith(text)}
                    self._completed_options = options
                else:
                    existing = full[:idx]
                    options = self.get_available_commands(existing)
                    self._completed_options = options
            else:
                options = self._completed_options
            # print(f"--- full: {full}, existing: {existing}, options: {options}")
            if text:
                matches = [s for s in options.keys() if s and s.startswith(text)]
            else:
                matches = list(options.keys())
            if state >= len(matches):
                return None
            response = matches[state] + ' '
        except:
            traceback.print_exc()
            response = None
            self._completed_options = None
        return response
    

    def show_completion_help(self, text, options, width):
        # get the help text in current context
        print("")
        print("Possible completions:")
        #print(f"In show_completion_help: text={text}, options={options}, width={width}")
        available_commands = self._completed_options
        if self.long_help:
            for item in options:
                k = item.ljust(width)
                description = available_commands.get(item.strip(), "")
                print(f"  {k} {description}")
        else:
            for i, item in enumerate(options):
                if i != 0 and i % 10 == 0:
                    print("")
                v = item.ljust(width)
                print(f"{v}", end=" ")
            print("")
        # show the prompt again
        prompt = self.get_prompt()
        line_buf = readline.get_line_buffer()
        print(f"{prompt}{line_buf}", end="", flush=True)
        
    def normal_mode_action(self, args: List[str]):
        print(f"normal_mode_action: {args}")
    
    def normal_mode_complete(self, args: List[str]) -> Dict[str, str]:
        return {
            "ping": "ping command",
            "upgrade": "upgrade command",
        }
    
    def normal_mode_show_action(self, args: List[str]):
        print(f"normal_mode_show_action: {args}")

    def normal_mode_show_complete(self, args: List[str]) -> Dict[str, str]:
        return {
            "hostname": "show hostname",
            "uptime": "show uptime",
        }
    
    def normal_mode_show_running_config_action(self, args: List[str]):
        print(f"normal_mode_show_running_config_action: {args}")

    def normal_mode_show_running_config_complete(self, args: List[str]) -> Dict[str, str]:
        return {
            "interface": "Interfaces configuration",
            "system": "System configuration",
        }
    
    def normal_mode_config_action(self, args: List[str]):
        print(f"normal_mode_config_action: {args}")
        self.mode = self.CONFIG

    def normal_mode_exit_action(self, args: List[str]):
        print(f"normal_mode_exit_action: {args}")
        raise EOFError()

    def config_mode_action(self, args: List[str]):
        print(f"config_mode_action: {args}")
        for x in args[:-1]:
            self.path.append(x)

    def config_mode_complete(self, args: List[str]) -> Dict[str, str]:
        return {
            "interface": "Interfaces configuration",
            "system": "System configuration",
        }
    
    def config_mode_exit_action(self, args: List[str]):
        print(f"config_mode_exit_action: {args}")
        if self.path:
            # pop last one
            self.path.pop()
        else:
            self.mode = self.NORMAL

    def config_mode_end_action(self, args: List[str]):
        print(f"config_mode_end_action: {args}")
        self.mode = self.NORMAL
        self.path = []

    def config_mode_top_action(self, args: List[str]):
        print(f"config_mode_top_action: {args}")
        self.path = []

    def config_mode_show_action(self, args: List[str]):
        print(f"config_mode_show_action: {args}")

    def config_mode_show_complete(self, args: List[str]) -> Dict[str,str]:
        return {}
    
    def config_mode_do_action(self, args: List[str]):
        print(f"config_mode_do_action: {args}")

    def config_mode_do_complete(self, args: List[str]) -> List[str]:
        return []
    
    def config_mode_no_action(self, args: List[str]):
        print(f"config_mode_no_action: {args}")

    def config_mode_no_complete(self, args: List[str]) -> Dict[str,str]:
        return {
            "interface": "Interfaces configuration",
            "system": "System configuration",
        }


class CommandLine:
    def __init__(self, ctx: CliContext):
        self.ctx = ctx

    def loop(self):
        try:
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("?: possible-completions")
            delims = readline.get_completer_delims()
            # dont use '-' for delim
            delims = delims.replace('-', '')
            readline.set_completer_delims(delims)
            readline.set_completer(self.ctx.complete)
            readline.set_completion_display_matches_hook(self.ctx.show_completion_help)
        except:
            pass

        line = ""
        while True:
            try:
                prompt = self.ctx.get_prompt()
                line = input(prompt)
                try:
                    self.ctx.execute(line)
                except KeyboardInterrupt:
                    # ignore ctrl+c
                    subprocess.run("reset", shell=True)
                    print("\r\n")
            except InputError as e:
                print(f"Input error: {e}")
            except (EOFError, SystemError, KeyboardInterrupt):
                print("\nBye")
                break
            except:
                print(f"Failed to run {line}")
                traceback.print_exc()
