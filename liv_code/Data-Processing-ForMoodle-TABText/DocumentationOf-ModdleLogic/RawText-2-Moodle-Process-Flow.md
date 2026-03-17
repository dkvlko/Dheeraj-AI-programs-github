
Revisiting UPTGT Kindle Book Processing for one single python code
1.Take Auto-Screenshots (Move to git hub folder)//OK
2.Split each photo in exact half vertically //OK
3.Convert each photo in text file.//OK (tessaract)
4.Stitch the text back into one single text file.//OK

Error detected : Delete special lines

5.Remove empty / whitespace-only lines from combined file //OK
6.Merge the lines of questions into one. //OK

Error detected:Need to merge lines again.

6.Delete everything except Questions ,Options and Answers//OK
7. Check IF the data is ready for Moodle formatting? If not add processor.
8.Run build_moodle.py over the file. //OK