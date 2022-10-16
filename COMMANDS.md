# Commands

## Only avaliable on a reply

* `quote`: Make a new quote image.
* `send_as_sticker`: Turn an image into a sticker.
* `multiquote [count]` / `forward_multiquote [count]`: (count is in [2, 6]) Make a new multiquote image.
* `avatar_changes`: Get the target user's avatar change history.
* `send_as_sticker`: Turns an image into a sticker.
* `tag [#tag]`: Tag a user. The tag will be shown in quote images.
* `remove_tag`: Removes tag of a user.

The difference between `multiquote` and `forward_multiquote` is the messages to quote. `multiquote` selects messages older than the target message, while `forward_multiquote` selects messages newer than the target message. Resulting image will always sort by time, however.

## Usable anywhere

* `archlinuxcn [package]`: Query a package in \[archlinuxcn\].
* `update_archlinuxcn`: Update the database used by `archlinuxcn` command.
* `emit_statistics`: Show statistics.
* `crazy_thursday`: On Thrusday, print "Crazy Thursday !!". Otherwise print remaining time to next Thursday.

## Others

* `send_avatar`: In a reply, send the avatar of the person being replied to. Outside of a reply, send the avatar of the command sender.