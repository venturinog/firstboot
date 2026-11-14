```
  ___               _          _ 
 |_ _|___ ___  __ _| |__   ___| |
  | |/ __/ __|/ _` | '_ \ / _ \ |
  | |\__ \__ \ (_| | |_) |  __/ |
 |___|___/___/\__,_|_.__/ \___|_|
```

Issabel is an open source distribution and GUI for Unified Communications systems forked from Elastix&copy;

It uses the [Asterisk©](http://www.asterisk.org/ "Asterisk Home Page") open source PBX software as its core.

First Boot
----

This module contains (or should contain) utilities and configurations that
cannot be prepared at install time from the ISO image, and are therefore
delayed until the first boot of the newly installed system.

On a fresh install the console sequence is:

1. `issabel-firstconfig.service` shows a "Wait for initial configuration"
   notice on `tty1` while MariaDB and Asterisk start. It only runs while
   `/installamp` exists, that is, while the IssabelPBX initialization is still
   pending.
2. `issabel-firstboot.service` takes `tty2` and initializes IssabelPBX there,
   then asks for the MariaDB root and web admin passwords.
3. `getty@tty1` is ordered after `issabel-firstboot`, so the console login
   appears only when the setup has finished. The ordering does not require
   success: if firstboot fails, its job ends and the login still appears.

`issabel-firstboot.service` returns the console to `tty1` and re-enables kernel
console messages from `ExecStopPost`, so a failed start does not leave the
console on `tty2` or muted. systemd's own unit status lines are kept off the
console of the installed system with `systemd.show_status=no` in its kernel
command line: they are written to `/dev/console`, which follows the active
virtual terminal, and would otherwise overwrite the notice and the dialogs.
They remain available in the journal.

Headless installations
----

The console flow needs a VGA console. On a server without one, connect over
SSH and run the initialization from the command line:

```
/usr/bin/issabel-admin-passwords --cli init <mariadb-root-password> <admin-password>
```

The notice and the dialogs are then not used; the IssabelPBX installation and
the deferred database scripts run from the same code path.


License
----

GPLv2 or Later

>This program is free software; you can redistribute it and/or
>modify it under the terms of the GNU General Public License
>as published by the Free Software Foundation; either version 2
>of the License, or (at your option) any later version.

>This program is distributed in the hope that it will be useful,
>but WITHOUT ANY WARRANTY; without even the implied warranty of
>MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
>GNU General Public License for more details.

>You should have received a copy of the GNU General Public License
>along with this program; if not, write to the Free Software
>Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
