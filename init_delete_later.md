# Whoopsync

### Specificaction
This is the Whoopsync project. The funciton of this project is to host a simple process
that periodically fetches data from the whoop api for a given list of user IDs.
The process should act as a unix/linux daemon that also logs its actions

### Entities
- main process
   - user list, being the users that are to be fetched from the whoop api
   - for each of the aspects that the whoop api tracks (sleep, workout etc) it asks the data manager
   when was the last update for that aspect, for that user, it asks the api for that data range, with a max
   data range specified in some .env file

- whoop api interface
  - abstracts away the api calls for ease of use.
  - manages errors
  - retry logic

- data manager
  - abstracted, receives the raw json from the server
  - main implementation uses sqlite that stores the data received for each user
