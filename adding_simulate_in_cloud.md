So we have changed to a newer version of sim4life (9.0) which supports running the fdtd simulations on the cloud. This is basically quite easy, will only require minor changes to how one actually runs the simulation once everything is setup. Specifically in 
src\simulation_runner.py:77-77
```
simulation.RunSimulation(wait=True)
```
you can add an argument that is something like server= or servers= (I forgot) and then you give an .Id of a server object. This is one of the items in the normal python list that one gets when calling .GetAvailableServers() (although idk in which sim4life module or object you would call it). 
So all in all, roughly there's like two main new lines of codes, in order for a simulation to be sent off into the cloud.
The servers items available have a .Name field which is a string. If they have the word SMALL or MEDIUM in them, that's a sign it's a remote server. and that's also how we're gonna select it.
So the idea basically is as follows. More generally, you wanna be able to implement the more general feature of submitting a job to some server.
For this to happen, manual isolve has to be false. Manual isolve is synonymous with running locally, but not through the Ares system which is buggy.
But if you wanna know, one could in theory set it to false and then have it be submitted to the server called 'localhost' which runs it through local Ares and yeah that would still be iSolve. Manual isolve is just a cmd subprocess iSolve.exe on the input file. What's cool is that you can also send it to another computer in the local network. So that would be a really usable feature. Anyways, I am rambling sorry if i confused you but it's quite easy, just implement that you can go select a server if manual isolve is false. 
HOWEVER, do add a warning system that IF you are running on the cloud, and for whatever reason things are failing, that's indication that the user should open the GUI and log in to sim4life.science with MFA. So that should be a big message to the user in this case.