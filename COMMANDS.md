# Commands

## Only avaliable on a reply

* `quote`: Make a new quote image.
* `send_as_sticker`: Turn an image into a sticker.
* `multiquote [count]` / `forward_multiquote [count]`: (count is in [2, 6]) Make a new multiquote image.
* `avatar_changes`: \[Depends on the database\] Get the target user's avatar change history.
* `name_changes`: \[Depends on the database\] Get the target user's name change history.
* `send_as_sticker`: Turns an image into a sticker.
* `tag [#tag]`: \[Depends on the database\] Tag a user. The tag will be shown in quote images.
* `remove_tag`: \[Depends on the database\] Removes tag of a user.
* `user_id`: Print the Matrix user ID of a user.

The difference between `multiquote` and `forward_multiquote` is the messages to quote. `multiquote` selects messages older than the target message, while `forward_multiquote` selects messages newer than the target message. Resulting image will always sort by time, however.

## Usable anywhere

* `archlinuxcn [package]`: Query a package in \[archlinuxcn\].
* `update_archlinuxcn`: Update the database used by `archlinuxcn` command.
* `emit_statistics`: \[Depends on the database\] Show statistics.
* `crazy_thursday`: On Thrusday, print "Crazy Thursday !!". Otherwise print remaining time to next Thursday.
* `room_id`: Print the Matrix Room ID.
* `ping`: Ping the bot, print the time the bot to receive the message.
* `last_message [sender]`: \[Depends on the database\] Gets the last event the `sender` has sent. `sender` must be a Matrix user ID.
* `lookup_message [external_url]`: \[Depends on the database\] Try to lookup the message with the given external URL in the database. Only properly works if the bridge sends the `external_url` data in the bridged message.

## Others

* `send_avatar`: In a reply, send the avatar of the person being replied to. Outside of a reply, send the avatar of the command sender.
* `wordcloud [all] [count]`: \[Depends on the database\] If the first paramter is `all`, builds a wordcloud of all the users in the last `count` days. Otherwise, when used in a reply, builds a wordcloud of the person being replied to. Outside of a reply, builds a wordcloud of the command sender.