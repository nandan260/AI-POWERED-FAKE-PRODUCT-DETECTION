// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract ProductVerification {

    struct Product {

        string serialNo;

        string manufacturer;

        string seller;

        string consumer;

        bool exists;
    }

    mapping(string => Product) public products;

    function registerProduct(
        string memory serialNo,
        string memory manufacturer
    ) public {

        products[serialNo] = Product(
            serialNo,
            manufacturer,
            "",
            "",
            true
        );
    }

    function assignSeller(
        string memory serialNo,
        string memory seller
    ) public {

        products[serialNo].seller = seller;
    }

    function assignConsumer(
        string memory serialNo,
        string memory consumer
    ) public {

        products[serialNo].consumer = consumer;
    }

    function verifyProduct(
        string memory serialNo
    )

    public

    view

    returns(

        string memory,

        string memory,

        string memory,

        bool

    )

    {

        Product memory p = products[serialNo];

        return(

            p.manufacturer,

            p.seller,

            p.consumer,

            p.exists

        );
    }
}