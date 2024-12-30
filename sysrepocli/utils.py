
# split a command into tokens
def split_command(s: str) -> "list[str]":
    result = []
    # states
    NORMAL = 1
    IN_QUOTE = 2
    t = ""
    q = ""
    state = NORMAL
    
    for c in s:
        if state == NORMAL:
            if c in [' ', '\t']:
                if t:
                    result.append(t)
                    t = ""
            else:
                if c == '|' or c == ';':
                    if t:
                        result.append(t)
                    result.append(c)
                    t = ""
                elif c in ['"', "'"]:
                    state = IN_QUOTE
                    q = c
                else:
                    t += c
        elif state == IN_QUOTE:
            if c == q:
                state = NORMAL
                result.append(t)
                t = ""
                q = ""
            else:
                t += c
                
    if t:
        result.append(t)
    
    return result



# For commands like this:
#  ['show', 'clock', ';', 'show', 'ont', ';', 'show', 'clock']
# this function returns:
#  [
#    ['show', 'clock'],
#    ['show', 'ont'],
#    ['show', 'clock']
#  ]
def command_groups(cmd: list[str]) -> list[list[str]]:
    result = []
    item = []
    for x in cmd:
        if x == ';':
            result.append(item)
            item = []
        else:
            item.append(x)
    if item:
        result.append(item)
    return result


# find the only element in the list that satisfies the predicate
# return None if there is more than one element that satisfies the predicate
def find_only(iter: list[str], predicate: callable):
    items = [x for x in iter if predicate(x) ]
    if len(items) == 1:
        return items[0]
    return None