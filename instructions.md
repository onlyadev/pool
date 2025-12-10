Task: Scrape information from YellowPages

Instructions: I would like you to write a python script that will scrape information from yellowpages (https://www.yellowpages.com/). For this, you will be using a pre-defined search string, and will need to scrape the results for that search string across a set of states listed below. The set of information we would like scraped will also be listed below. The output should be a CSV file with columns for each of the fields we would like scraped.

Search string: pool cleaning and maintenance

Information to scrape: Name, Business website (if available or "N/A" if not), Business phone number, Categories/tags (these are wrapped in a Div class called 'categories'), State

States: FL, CA, TX, AZ, NY, NJ, PA, OH, MI, MA
Expected Number per state: 2700,2700,2700, 2700, 1400,1400,1200,1100,600,500

Additional context: You will likely need to use beautifulsoup for this unless you can find a way to scrape the APIs in question. You should also consider using url manipulation to do direct searches for results. Here's an example of the URL for the 2nd page of results for the search string above in Texas (https://www.yellowpages.com/search?search_terms=pool%20cleaning%20and%20maintenance&geo_location_terms=TX&page=2). Feel free to ask me any questions along the way