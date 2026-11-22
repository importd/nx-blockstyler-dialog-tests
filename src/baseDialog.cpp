


//------------------------------------------------------------------------------
//These includes are needed for the following template code
//------------------------------------------------------------------------------
#define USER_EXIT_OR_MENU 1
#include "baseDialog.hpp"
#ifdef AUTODLG_TEST
#include "autodlg_test.h"
#endif
using namespace NXOpen;
using namespace NXOpen::BlockStyler;

//------------------------------------------------------------------------------
// Initialize static variables
//------------------------------------------------------------------------------
Session *(baseDialog::theSession) = NULL;
UI *(baseDialog::theUI) = NULL;
//------------------------------------------------------------------------------
// Constructor for NX Styler class
//------------------------------------------------------------------------------
baseDialog::baseDialog()
{
    try
    {
        // Initialize the NX Open C++ API environment
        baseDialog::theSession = NXOpen::Session::GetSession();
        baseDialog::theUI = UI::GetUI();
        theDlxFileName = "baseDialog.dlx";
        theDialog = baseDialog::theUI->CreateDialog(theDlxFileName);
        // Registration of callback functions
        theDialog->AddApplyHandler(make_callback(this, &baseDialog::apply_cb));
        theDialog->AddOkHandler(make_callback(this, &baseDialog::ok_cb));
        theDialog->AddUpdateHandler(make_callback(this, &baseDialog::update_cb));
        theDialog->AddFilterHandler(make_callback(this, &baseDialog::filter_cb));
        theDialog->AddInitializeHandler(make_callback(this, &baseDialog::initialize_cb));
        theDialog->AddDialogShownHandler(make_callback(this, &baseDialog::dialogShown_cb));
    }
    catch(exception& ex)
    {
        //---- Enter your exception handling code here -----
        throw;
    }
}

//------------------------------------------------------------------------------
// Destructor for NX Styler class
//------------------------------------------------------------------------------
baseDialog::~baseDialog()
{
    if (theDialog != NULL)
    {
        delete theDialog;
        theDialog = NULL;
    }
}

#if USER_EXIT_OR_MENU
    extern "C" DllExport void  ufusr(char *param, int *retcod, int param_len)
    {
        baseDialog *thebaseDialog = NULL;
        try
        {
            thebaseDialog = new baseDialog();
            // The following method shows the dialog immediately
            thebaseDialog->Show();
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
        if(thebaseDialog != NULL)
        {
            delete thebaseDialog;
            thebaseDialog = NULL;
        }
    }
#endif//USER_EXIT_OR_MENU
#if USER_EXIT
    
    //------------------------------------------------------------------------------
    // This method specifies how a shared image is unloaded from memory
    // within NX. This method gives you the capability to unload an
    // internal NX Open application or user  exit from NX. Specify any
    // one of the three constants as a return value to determine the type
    // of unload to perform:
    //
    //
    //    Immediately : unload the library as soon as the automation program has completed
    //    Explicitly  : unload the library from the "Unload Shared Image" dialog
    //    AtTermination : unload the library when the NX session terminates
    //
    //
    // NOTE:  A program which associates NX Open applications with the menubar
    // MUST NOT use this option since it will UNLOAD your NX Open application image
    // from the menubar.
    //------------------------------------------------------------------------------
    extern "C" DllExport int ufusr_ask_unload()
    {
        //return (int)Session::LibraryUnloadOptionExplicitly;
        return (int)Session::LibraryUnloadOptionImmediately;
        //return (int)Session::LibraryUnloadOptionAtTermination;
    }
    
    //------------------------------------------------------------------------------
    // Following method cleanup any housekeeping chores that may be needed.
    // This method is automatically called by NX.
    //------------------------------------------------------------------------------
    extern "C" DllExport void ufusr_cleanup(void)
    {
        try
        {
            //---- Enter your callback code here -----
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
    }
#endif//USER_EXIT
    
    int baseDialog::Show()
    {
        try
        {
            theDialog->Show();
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
        return 0;
    }
    
#if CALLBACK
    //------------------------------------------------------------------------------
    //Method name: Show_baseDialog
    //------------------------------------------------------------------------------
    void baseDialog::Show_baseDialog()
    {
        baseDialog *thebaseDialog = NULL;
        try
        {
            thebaseDialog = new baseDialog();
            // The following method shows the dialog immediately
            thebaseDialog->Show();
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
        if(thebaseDialog != NULL)
        {
            delete thebaseDialog;
            thebaseDialog = NULL;
        }
    }
#endif//CALLBACK
    
    //------------------------------------------------------------------------------
    //---------------------Block UI Styler Callback Functions--------------------------
    //------------------------------------------------------------------------------
    
    //------------------------------------------------------------------------------
    //Callback Name: initialize_cb
    //------------------------------------------------------------------------------
    void baseDialog::initialize_cb()
    {
        try
        {
            group0 = dynamic_cast<NXOpen::BlockStyler::Group*>(theDialog->TopBlock()->FindBlock("group0"));
            selection0 = dynamic_cast<NXOpen::BlockStyler::SelectObject*>(theDialog->TopBlock()->FindBlock("selection0"));
            enum0 = dynamic_cast<NXOpen::BlockStyler::Enumeration*>(theDialog->TopBlock()->FindBlock("enum0"));
            linear_dim0 = dynamic_cast<NXOpen::BlockStyler::LinearDimension*>(theDialog->TopBlock()->FindBlock("linear_dim0"));
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
    }
    
    //------------------------------------------------------------------------------
    //Callback Name: dialogShown_cb
    //This callback is executed just before the dialog launch. Thus any value set 
    //here will take precedence and dialog will be launched showing that value. 
    //------------------------------------------------------------------------------
    void baseDialog::dialogShown_cb()
    {
        try
        {

            //---- Enter your callback code here -----
#ifdef AUTODLG_TEST
    AUTODLG_HOOK(theDialog, "selection0", "enum0", "linear_dim0");
#endif
}
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
    }
    
    //------------------------------------------------------------------------------
    //Callback Name: apply_cb
    //------------------------------------------------------------------------------
    int baseDialog::apply_cb()
    {
        int errorCode = 0;
        try
        {
            //---- Enter your callback code here -----
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            errorCode = 1;
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
        return errorCode;
    }
    
    //------------------------------------------------------------------------------
    //Callback Name: update_cb
    //------------------------------------------------------------------------------
    int baseDialog::update_cb(NXOpen::BlockStyler::UIBlock* block)
    {
        try
        {
            if(block == selection0)
            {
            //---------Enter your code here-----------
            }
            else if(block == enum0)
            {
            //---------Enter your code here-----------
            }
            else if(block == linear_dim0)
            {
            //---------Enter your code here-----------
            }
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
        return 0;
    }
    
    //------------------------------------------------------------------------------
    //Callback Name: ok_cb
    //------------------------------------------------------------------------------
    int baseDialog::ok_cb()
    {
        int errorCode = 0;
        try
        {
            errorCode = apply_cb();
        }
        catch(exception& ex)
        {
            //---- Enter your exception handling code here -----
            errorCode = 1;
            baseDialog::theUI->NXMessageBox()->Show("Block Styler", NXOpen::NXMessageBox::DialogTypeError, ex.what());
        }
        return errorCode;
    }
    
    //------------------------------------------------------------------------------
    //Callback Name: filter_cb
    //------------------------------------------------------------------------------
    int baseDialog::filter_cb(NXOpen::BlockStyler::UIBlock* block, NXOpen::TaggedObject* selectObject)
    {
        return(UF_UI_SEL_ACCEPT);
    }
    
    //------------------------------------------------------------------------------
    //Function Name: GetBlockProperties
    //Description: Returns the propertylist of the specified BlockID
    //------------------------------------------------------------------------------
    PropertyList* baseDialog::GetBlockProperties(const char *blockID)
    {
        return theDialog->GetBlockProperties(blockID);
    }
