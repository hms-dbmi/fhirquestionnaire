$(function() {

    function showDependent(container, checkbox) {

        // Check for repositioning
        if(!$(container).data('detached')) {

            // Place the element next to the input
            $(checkbox).parent().parent().append(container);
        }

        // Show it
        $(container).show();

        // Mark all inputs
        $(container).find('input[data-required="true"]').addBack().each(function(index, element) {
            $(element).attr('required', 'required');
        });
    }

    function hideDependent(container, checkbox) {

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

        // Get all dependent inputs
        var dependents = $('[data-enabled-when="' + enabledWhen + '"]');

        // Check for none
        if (!dependents.length) {

            // If this is radio input, we need to hide dependent inputs
            if ($(this).attr("type") == "radio") {

                // Find all dependents
                $('[data-parent="' + _name + '"]').each(function() {

                    // Get the element
                    var container = $(this);

                    // Hide it
                    hideDependent(container, checkbox);
                });
            }
        } else {

            // Manage dependent inputs
            $.each(dependents, function() {

                // Get the element
                var container = $(this);

                // Move the element
                if(checked) {

                    // Show it
                    showDependent(container, checkbox);

                } else {

                    // Hide it
                    hideDependent(container, checkbox);
                }
            });
        }
    });
});
