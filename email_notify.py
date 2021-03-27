import yagmail

sender = "ni.rram.status@gmail.com"
pw = "allen128x"
receiver = "lihaitong.pku@gmail.com"
body = "NI-RRAM Status: Testing Finished."


yag = yagmail.SMTP(sender, pw)
yag.send(
    to=receiver,
    subject="NI-RRAM Status: Testing Finished.",
    contents=body
)