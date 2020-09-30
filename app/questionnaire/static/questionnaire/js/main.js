$(function() {

    // Add a handler that triggers on assignment as well as on the specified event
    jQuery.fn.nowAndOn = function (event, handler) {
        this.each(function () {
            handler.call(this);
        });
        this.bind(event, handler);
        return this;
    };

    $('[data-details!=""]').nowAndOn('change', function (){

        // Get the ID
        var checkbox = $(this);
        var _name = $(this).data('details');
        if( ! _name ) return;

        // See if checked
        var checked = this.checked;

        // Get this value
        var value = $(this).val();

        // Check for a detail input
        var enabledWhen = _name + '\=' + value;
        $('[data-enabled-when="' + enabledWhen + '"]').each(function() {

            // Get the element
            var container = $(this);

            // Move the element
            if(checked) {

                // Check for repositioning
                if(!$(container).data('detached')) {

                    // Place the element next to the input
                    $(checkbox).parent().parent().append($(this));
                }

                // Show it
                $(container).show();

                // Mark all inputs
                $(container).find('input[data-required="true"]').addBack().each(function(index, element) {
                    $(element).attr('required', 'required');
                });

            } else {

                // Show it
                $(container).hide();

                // Find all inputs
                $(container).find('input').addBack().each(function(index, element) {

                    // Mark child inputs as required
                    $(element).removeAttr('required');

                    // Check if date input
                    if($(element).hasClass('datepickerinput')) {
                        // Clear the date field
                        var data = JSON.parse($(element).attr('dp_config'));
                        var datepickerelement = $(element).datetimepicker(data.options);
                        var datepickerdata = $(datepickerelement).data("DateTimePicker");
                        datepickerdata.clear();
                    } else {
                        // Clear value
                        $(element).removeAttr('value');
                        $(element).val('');
                    }
                });
            }
        });
    });
});
