# 1，Start up
 
Open start_windows.

![alt text](images/image.png)

Start at :http://127.0.0.1:8000/

![alt text](images/image-1.png)

(optional->web server, you can check it or jump this step)
After start the server on localhost, Download ngrok, create account and set up. Tips: You can read docs of ngrok in this network: https://ngrok.com/docs/what-is-ngrok to learn how to use it.
After set up, click the ngork.exe, and input ‘ngrok http 8000’，and see this interface:

![alt text](images/image-2.png)

Input the url in the line “Forwarding” in any remote laptop, and you can open our system! The interface work on local/remote.

![alt text](images/image-3.png)
![alt text](images/image-4.png)
 


# 2, login function
Input any one of our demo account as user name, and pass1234 as password.

![alt text](images/image-5.png)

# 3, Create account
Login as HR,  click the button “create account” below left side “menu”.

![alt text](images/image-6.png)

Select username, password and role for them. If you create a TA account or casual account, you can choose it to be a phd or non-phd account.

![alt text](images/image-7.png)

Click the button account to see all accounts!

![alt text](images/image-8.png)

# 4, Create course
Click the button course or dashboard, to see the courses we have(You can check the unit coordinator of each course in this page):

![alt text](images/image-9.png)

Click the button new course, to see this interface:

![alt text](images/image-10.png)

Enter code, name, UC, budget, start/end time, time slots of the course, and save.
Notice: In this project, we will use a demo account and a course for demonstration. If you would like to use more accounts for testing, you can create your own courses or accounts, but we recommend that you first follow the instructions below to operate with the demo accounts and course.
# 5, TA application
Login by any TA account, and click the button TA Request, the blue button “Apply as TA” can go to the TA apply interface, while “My TA Application” button can go to request check interface.

![alt text](images/image-11.png)

Choose the course, (we choose comp5310), and submit it.(Click the Dashboard button so the menu can recover, please do it at anytime you find the buttons under menu change)

![alt text](images/image-12.png)
![alt text](images/image-13.png)

Logout and use UC account login. The UC of comp5310 is uc_1.

![alt text](images/image-14.png)

Click “unit coordinator inbox in the left side”, and click “Open TA Request Inbox”.

![alt text](images/image-15.png)

Choose “Forward to HR” or reject.
Use HR login, click the button “HR Inbox” under menu, and click “Open TA Request Inbox”.

![alt text](images/image-16.png)
![alt text](images/image-17.png)

Choose approve or reject. The workflow complete. TA can find this/her course now!

![alt text](images/image-18.png)

# 6, Casual application
Login as causal, and see this interface(Dashboard/My request)

![alt text](images/image-19.png)

Click the green button “new”, to enter this interface

![alt text](images/image-20.png)

Choose course(we choose comp5310), send to who(UC or TA of this course, we choose TA), and time(we choose 16:00-17:00). Save application. 

![alt text](images/image-21.png)

You can submit, edit, or delete it. Let’s submit the application.
Use the account of TA or UC of this course. (We choose send to TA, so use ta_debug).  
Click ta_inbox under menu, enter comment and forward to UC.

![alt text](images/image-22.png)

Use the account of UC of this courses to login(use uc_1 to login this time). Click unit coordinator inbox under menu. Click View TA comment to see the comment of TA, choose approve or reject button.(Choose approve to continue)

![alt text](images/image-23.png)

Use HR login, and click HR inbox under menu, approve(finalize) or reject it.

![alt text](images/image-24.png)

Casual can check his/her application:

![alt text](images/image-25.png)

Click “view” to see detail(hourly rate and total pay of this course) of application, or resubmit it. We can see the hourly rate is for non-phd user. You can check whether a casual is a phd or not by click the button “My profile”. 

![alt text](images/image-26.png)

# 7, Time slot change(allocation) function
Use a UC account to login(we use uc_1), click “change request” under menu.

![alt text](images/image-27.png)

Click the “New” button.

![alt text](images/image-28.png)

Choose target casual and time slots(if you want to choose multiple slots, push ctrl and click). We choose two slots for casual_debug1. Save and send.
Use casual login(Casual_debug1), click change request button under menu. Approve or reject it.

![alt text](images/image-29.png)

After approve, use HR login. Click the change request button under menu, choose approve or reject.

![alt text](images/image-30.png)

We can see that the new time slots has already change, casual_debug1 has two time slots now(you can see it in dashboard of UC_1 or ta_debug):

![alt text](images/image-31.png)

And you can also see the new slots in casual’s dashboard.

![alt text](images/image-32.png)

# 8, Total hour add/subtract
Login by UC_1 account, click the button courses under menu. Both UC and TA has this function, so you can also use ta_debug to test this function.

![alt text](images/image-33.png)

If you click the button view, you can see the detail of this course:
For comp5310, we can see the casual and TA of this course, and hourly rate, total pay of each casual, and budget use of this course.

![alt text](images/image-34.png)

If you Click ‘adjust’ button in the last interface(My Courses),  choose hourly rate(first time/repeat hourly rate), and add/subtract hours, positive number for add, negative number for subtract. Click save.

![alt text](images/image-35.png)

This function will take effective immediately, and doesn’t have a workflow.  We add 1 hour, and choose repeat rate, and let’s see what happen:

![alt text](images/image-36.png)


UC/TA(My course->view):

![alt text](images/image-37.png)

Casual(My request->view):

![alt text](images/image-38.png)

# 9, Message
Use any account to login, and click message button under menu, click compose, choose target user, subject and input information. Sent this message.

![alt text](images/image-39.png)

Use the target’s account login(uc_1), click inbox and see the message:

![alt text](images/image-40.png)
