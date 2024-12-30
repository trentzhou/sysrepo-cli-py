#!/usr/bin/env python3
from sysrepocli import CommandLine, CliContext, SchemaContext
import sysrepo

if __name__ == "__main__":
    with sysrepo.connection.SysrepoConnection() as conn:
        with conn.start_session() as sess:
            sc = SchemaContext(sess)
            ctx = CliContext(sc)
            cli = CommandLine(ctx)
            cli.loop()
