/* parts of this file (particularly configure(), search(), and update()) draw from Harvard's CS50 PSET8 */

// Google map
var map;

// styles for map: https://developers.google.com/maps/documentation/javascript/styling
var styles = [
    {
        "featureType": "administrative.land_parcel",
        "elementType": "labels",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "poi",
        "elementType": "labels.text",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "poi.business",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "road",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "road",
        "elementType": "labels.icon",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "road.local",
        "elementType": "labels",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "transit",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    }
];

// options for map: https://developers.google.com/maps/documentation/javascript/reference#MapOptions
var options = {
    center: {lat: 39.0183, lng: -95.9369}, // center of US
    disableDefaultUI: true,
    mapTypeId: google.maps.MapTypeId.ROADMAP,
    maxZoom: 14,
    panControl: true,
    styles: styles,
    zoom: 4,
    zoomControl: true
};

// markers for map
var markers = [];

// info window
var info = new google.maps.InfoWindow();

// when info window is fully loaded
google.maps.event.addListener(info, 'domready', function() {
    
    // load audio upon request
    playRequest();
});

// when DOM is fully loaded
$(function() {

    // load audio upon request
    playRequest();

    // check if user is on index/'map' page
    if (window.location.href.split('/').pop() == '') {

        // get div container for map
        var canvas = $("#map-canvas").get(0);

        // instantiate map
        map = new google.maps.Map(canvas, options);

        // configure UI once Google Map is idle (i.e., loaded)
        google.maps.event.addListenerOnce(map, "idle", configure);
    }
});


function configure()
{
    // update UI after map has been dragged
    google.maps.event.addListener(map, "dragend", function() {

        // if info window isn't open - http://stackoverflow.com/a/12410385
        if (!info.getMap || !info.getMap()) {
            update();
        }
    });

    // update UI after zoom level changes
    google.maps.event.addListener(map, "zoom_changed", function() {
        update();
    });

    // configure typeahead
    $("#q").typeahead({
        highlight: false,
        minLength: 1
    },
    {
        display: function(suggestion) { return null; },
        limit: 10,
        source: search,
        templates: {
            suggestion: Handlebars.compile(
                "<div>" +
                "{{name}}, {{city}}, {{state}}" +
                "</div>"
            )
        }
    });

    // re-center map after place is selected from drop-down
    $("#q").on("typeahead:selected", function(eventObject, suggestion, name) {

        // set map's center
        map.setCenter({lat: parseFloat(suggestion.lat), lng: parseFloat(suggestion.lng)});
        map.setZoom(7);

        // update UI
        update();
    });

    // hide info window when text box has focus
    $("#q").focus(function(eventData) {
        info.close();
    });

    // update UI
    update();

    // give focus to text box
    $("#q").focus();
}


function search(query, syncResults, asyncResults)
{
    // get places matching query (asynchronously)
    var parameters = {
        q: query
    };
    $.getJSON(Flask.url_for("search"), parameters)
    .done(function(data, textStatus, jqXHR) {

        // call typeahead's callback with search results
        asyncResults(data);
    })
    .fail(function(jqXHR, textStatus, errorThrown) {

        // log error to browser's console
        console.log(errorThrown.toString());

        // call typeahead's callback with no results
        asyncResults([]);
    });
}


function update() 
{
    // get map's bounds
    var bounds = map.getBounds();
    var ne = bounds.getNorthEast();
    var sw = bounds.getSouthWest();

    // get places within bounds (asynchronously)
    var parameters = {
        ne: ne.lat() + "," + ne.lng(),
        sw: sw.lat() + "," + sw.lng()
    };
    $.getJSON(Flask.url_for("update"), parameters)
    .done(function(data, textStatus, jqXHR) {

        // remove old markers from map
        removeMarkers();

        // add new markers to map
        for (var i = 0; i < data.length; i++) {
            addMarker(data[i]);
        }
    })
    .fail(function(jqXHR, textStatus, errorThrown) {

        // log error to browser's console
        console.log(errorThrown.toString());
    });
}


function addMarker(station)
{
    // get lat and lng
    var latLng = {
        lat: station.lat,
        lng: station.lng
    };

    // instantiate icon
    var icon = {
        labelOrigin: new google.maps.Point(8, 48),
        // https://openclipart.org/detail/275123/signal-tower
        url: Flask.url_for('static', {filename: 'signaltower.png'})
    };

    // instantiate marker
    var marker = new google.maps.Marker({
        map: map,
        position: latLng,
        title: station.name,
        //label: station.name,
        icon: icon
    });

    // listen for clicks on marker
    marker.addListener('click', function() {
    
        // declare variable for html storage
        var content;

        // set parameters for /lookup request
        var parameters = {
            city: station.city,
            state: station.state
        };

        // get JSON objects of stations with geo parameter
        $.getJSON(Flask.url_for("lookup"), parameters)
        .done(function(data, textStatus, jqXHR) {

            // start unordered list
            content = "<div class='station_info'>";

            // build info for each station for given city/state
            for (var i = 0; i < data.length; i++) {
                content += "<h4 align='center'><a href='" + data[i].url_site + "' target='_blank'>" + data[i].name + "</a>&nbsp;&nbsp;";
                content += "<button id='play' value='" + data[i].url_stream + "' class='btn btn-default btn-sm play'>listen</button></h4>";
                content += "<ul>";
                content += "<li>" + data[i].call + "</li>";
                content += "<li>" + data[i].city + ", " + data[i].state + "</li>";
                content += "<li>Tune in: " + data[i].freq + "</li>";
                content += "<li>" + data[i].power + " watts</li>";
                content += "</ul>";
                content += "<hr/>";
            }

            // end unordered list
            content += "</div>";

            // pass content string of articles to info window for marker
            showInfo(marker, content);
        })
        .fail(function(jqXHR, textStatus, errorThrown) {

            // log error to browser's console
            console.log(errorThrown.toString());
        }); // end of getJSON

    }); // end of marker listener

    // store marker
    markers.push(marker);

}


function removeMarkers()
{
    // iterate over array from top to bottom
    for (var i = markers.length - 1; i >= 0; i--) {

        // remove marker from map
        markers[i].setMap(null);

        // remove item from array
        markers.pop(i);
    }
}


function showInfo(marker, content)
{
    // start div
    var div = "<div id='info'>";
    if (typeof(content) == "undefined") {
        // http://www.ajaxload.info/
        div += "<span>loading...</span>";
    }
    else {
        div += content;
    }

    // end div
    div += "</div>";

    // set info window's content
    info.setContent(div);

    // open info window (if not already open)
    info.open(map, marker);
}


function playRequest()
{
    // listen for play button clicks
    $( ".play" ).click(function(event) {
        event.preventDefault();

        // set value of button clicked to media player source
        $('#stream').attr("src", $( this ).val());

        // load and play media
        var player = $('#player').get(0);
        player.load();
        player.play();


        /* get currently playing station info */

        // set parameters for /lookup request
        var parameters = {
            stream: $( this ).val()
        };

        // declare html storage to load to window
        var content;

        // get JSON object of station with stream url parameter
        $.getJSON(Flask.url_for("lookup"), parameters)
        .done(function(data, textStatus, jqXHR) {

            // array of 1 result returned, renamed for clarity
            data = data[0];

            content = "<h4><a href='" + data.url_site + "' target='_blank'>" + data.name + " (" + data.call + ")</a></h4>";
            content += "<p>" + data.city + ", " + data.state + "</br>";
            content += "Tune in: " + data.freq + "</br>";
            content += data.power + " watts</p>";

            // load station info to side panel
            $('#station-info').html(content);
        })
        .fail(function(jqXHR, textStatus, errorThrown) {

            // log error to browser's console
            console.log(errorThrown.toString());
        }); // end of getJSON

    }); // end of button.click function
}
